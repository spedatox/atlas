"""Switchable local SQLite / authenticated HTTP storage for the desktop app."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from database import DatabaseManager
from inventory_io import MAX_FILE_SIZE, read_document, write_document, validate_document


class BackendError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, 'API redirects are disabled', headers, fp)


def normalize_url(url):
    url = url.strip().rstrip('/')
    parts = urlsplit(url)
    if (parts.scheme not in ('https', 'http') or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment):
        raise ValueError('Geçerli bir HTTPS sunucu adresi girin.')
    if parts.scheme == 'http' and parts.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Uzak bağlantılar HTTPS kullanmalı. HTTP yalnızca localhost için kullanılabilir.')
    return url


def settings_path():
    if os.environ.get('ATLAS_CONFIG_PATH'):
        return Path(os.environ['ATLAS_CONFIG_PATH'])
    base = Path(os.environ.get('APPDATA', Path.home() / '.config'))
    return base / 'ATLAS' / 'settings.json'


def load_settings():
    path = settings_path()
    settings = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError('Geçersiz ATLAS yapılandırması.')
    return {'backend': os.environ.get('ATLAS_BACKEND', settings.get('backend', 'local')),
            'url': os.environ.get('ATLAS_REMOTE_URL', settings.get('url', ''))}


def save_settings(settings):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Tokens and user passwords are deliberately never persisted here.
    write_document(path, {'backend': settings['backend'], 'url': settings.get('url', '')})


class RemoteBackend:
    def __init__(self, url, token, timeout=10):
        self.url = normalize_url(url)
        if not token or '\r' in token or '\n' in token:
            raise ValueError('API anahtarı gerekli (ATLAS_API_TOKEN veya bağlantı penceresi).')
        self._token = token
        self._session = None
        self.timeout = timeout

    def _request(self, method, path, payload=None):
        headers = {'Authorization': f'Bearer {self._token}', 'Accept': 'application/json'}
        if self._session:
            headers['X-Atlas-Session'] = self._session
        body = None
        if payload is not None:
            body = json.dumps(payload, allow_nan=False).encode('utf-8')
            if len(body) > MAX_FILE_SIZE:
                raise BackendError('İstek 50 MiB sınırını aşıyor.')
            headers['Content-Type'] = 'application/json'
        request = Request(self.url + '/api/v1/' + path, data=body, headers=headers, method=method)
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self.timeout) as response:
                # Never forward credentials to redirects or a different API.
                if response.url != request.full_url:
                    raise BackendError('API yönlendirmesi desteklenmiyor; doğrudan sunucu adresini kullanın.')
                raw = response.read(MAX_FILE_SIZE + 1)
                if len(raw) > MAX_FILE_SIZE:
                    raise BackendError('Sunucu yanıtı çok büyük.')
                return json.loads(raw)
        except HTTPError as exc:
            messages = {400: 'Geçersiz kayıt veya yedek dosyası.',
                        401: 'API anahtarı geçersiz.', 403: 'Oturum sona erdi; yeniden giriş yapın.',
                        404: 'Kayıt veya API bulunamadı; envanteri yenileyin.',
                        409: 'Kayıt çakışması veya geçersiz sunucu ilişkisi.',
                        413: 'Dosya çok büyük.', 429: 'Çok fazla giriş denemesi; bir dakika bekleyin.'}
            raise BackendError(messages.get(exc.code, f'Sunucu isteği başarısız (HTTP {exc.code}).')) from None
        except (URLError, TimeoutError, OSError):
            raise BackendError('Uzak sunucuya bağlanılamadı. Adresi, ağı ve TLS sertifikasını kontrol edin.') from None
        except (ValueError, UnicodeError):
            raise BackendError('Sunucu geçerli bir ATLAS yanıtı vermedi.') from None

    def check_connection(self):
        result = self._request('GET', 'health')
        if not isinstance(result, dict) or result.get('service') != 'atlas' or result.get('version') != 1:
            raise BackendError('Uyumsuz ATLAS sunucusu.')
        return result

    def authenticate(self, username, password):
        self._session = None
        result = self._request('POST', 'login', {'username': username, 'password': password})
        self._session = result.get('session')
        return bool(self._session)

    def get_inventory(self):
        return self._request('GET', 'inventory')

    def get_server(self, server_id):
        return self._request('GET', f'servers/{server_id}')

    def get_vm(self, vm_id):
        return self._request('GET', f'vms/{vm_id}')

    def add_server(self, data):
        return self._request('POST', 'servers', data)['id']

    def add_vm(self, data):
        return self._request('POST', 'vms', data)['id']

    def update_server(self, server_id, data):
        self._request('PUT', f'servers/{server_id}', data)

    def update_vm(self, vm_id, data):
        self._request('PUT', f'vms/{vm_id}', data)

    def delete_server(self, server_id):
        self._request('DELETE', f'servers/{server_id}')

    def delete_vm(self, vm_id):
        self._request('DELETE', f'vms/{vm_id}')

    def export_backup(self, destination):
        write_document(destination, validate_document(self._request('GET', 'backup')))
        return str(destination)

    def create_backup(self, destination=None):
        if destination is not None:
            return self.export_backup(destination)
        return self._request('POST', 'backup')['backup_path']

    def import_file(self, source, mode='merge'):
        return self.import_document(read_document(source), mode)

    def import_document(self, document, mode='merge'):
        document = validate_document(document)
        if mode not in ('merge', 'replace'):
            raise ValueError('İçe aktarma modu merge veya replace olmalı.')
        return self._request('POST', 'import', {'document': document, 'mode': mode})


class BackendProxy:
    """Stable reference shared by login and main window; no silent local fallback."""
    def __init__(self):
        self._backend = None
        self.mode = None

    def configure(self, settings, token=None):
        mode = settings.get('backend', 'local')
        if mode == 'remote':
            backend = RemoteBackend(settings.get('url', ''), token or os.environ.get('ATLAS_API_TOKEN', ''))
            backend.check_connection()
        elif mode == 'local':
            backend = DatabaseManager(os.environ.get('ATLAS_DB_PATH'))
        else:
            raise ValueError('Bilinmeyen veri kaynağı.')
        self._backend = backend
        self.mode = mode

    def __getattr__(self, name):
        if self._backend is None:
            self.configure(load_settings())
        return getattr(self._backend, name)


db_manager = BackendProxy()
