"""ATLAS API. Bind to loopback behind an HTTPS reverse proxy for remote access."""
import argparse
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from database import DatabaseManager
from inventory_io import MAX_FILE_SIZE

LOG = logging.getLogger('atlas.server')


class AtlasServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, database, token):
        if not token or len(token) < 32 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError('ATLAS_API_TOKEN en az 32 ASCII karakter içermeli (boşluk kullanmayın).')
        self.database = database
        self.token = token
        self.sessions = {}
        self.login_attempts = {}
        self.auth_lock = threading.Lock()
        super().__init__(address, AtlasHandler)


class AtlasHandler(BaseHTTPRequestHandler):
    server_version = 'ATLAS/1'

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *_args):
        # Paths, authorization headers, and request bodies never enter access logs.
        pass

    def _reply(self, code, data):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('JSON required')
        if self.headers.get('Transfer-Encoding'):
            raise ValueError('Chunked requests are unsupported')
        length = int(self.headers.get('Content-Length', '-1'))
        if length < 0:
            raise ValueError('Content-Length required')
        if length > MAX_FILE_SIZE:
            raise OverflowError('Payload too large')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete body')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('JSON object required')
        return data

    def _has_session(self):
        now = time.monotonic()
        with self.server.auth_lock:
            self.server.sessions = {key: expiry for key, expiry in self.server.sessions.items() if expiry > now}
            return self.headers.get('X-Atlas-Session', '') in self.server.sessions

    def _login(self):
        data = self._body()
        username, password = data.get('username'), data.get('password')
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError('Credentials required')
        now = time.monotonic()
        with self.server.auth_lock:
            # Global budget also protects deployments behind a loopback proxy.
            attempts = [t for t in self.server.login_attempts.get('all', []) if now - t < 60]
            self.server.login_attempts['all'] = attempts
            if len(attempts) >= 20:
                self._reply(429, {'error': 'Too many login attempts'})
                return
            attempts.append(now)
        if not self.server.database.authenticate(username, password):
            self._reply(200, {'session': None})
            return
        session = secrets.token_urlsafe(32)
        with self.server.auth_lock:
            self.server.sessions = {key: expiry for key, expiry in self.server.sessions.items() if expiry > now}
            if len(self.server.sessions) >= 1000:
                self._reply(429, {'error': 'Session limit reached'})
                return
            self.server.sessions[session] = now + 12 * 60 * 60
        self._reply(200, {'session': session})

    def _handle(self):
        # Authenticate even health checks; all data routes also require app login.
        authorization = self.headers.get('Authorization', '')
        if not hmac.compare_digest(authorization.encode('utf-8'), f'Bearer {self.server.token}'.encode('utf-8')):
            self._reply(401, {'error': 'Invalid API token'})
            return
        path = urlsplit(self.path).path
        if path == '/api/v1/health' and self.command == 'GET':
            self._reply(200, {'service': 'atlas', 'version': 1})
            return
        if path == '/api/v1/login' and self.command == 'POST':
            self._login()
            return
        if not self._has_session():
            self._reply(403, {'error': 'Login required'})
            return
        db = self.server.database
        if path == '/api/v1/inventory' and self.command == 'GET':
            self._reply(200, db.get_inventory())
        elif path == '/api/v1/backup' and self.command == 'GET':
            self._reply(200, db.export_document())
        elif path == '/api/v1/backup' and self.command == 'POST':
            self._reply(201, {'backup_path': db.create_backup()})
        elif path == '/api/v1/import' and self.command == 'POST':
            data = self._body()
            self._reply(200, db.import_document(data.get('document'), data.get('mode', 'merge')))
        else:
            parts = path.split('/')
            if len(parts) not in (4, 5) or parts[1:3] != ['api', 'v1'] or parts[3] not in ('servers', 'vms'):
                raise LookupError('Unknown route')
            table = parts[3]
            singular = 'server' if table == 'servers' else 'vm'
            if len(parts) == 4 and self.command == 'POST':
                row_id = getattr(db, 'add_' + singular)(self._body())
                self._reply(201, {'id': row_id})
                return
            if len(parts) != 5 or not parts[4].isdigit() or not 0 < int(parts[4]) <= 2**63 - 1:
                raise LookupError('Unknown route')
            row_id = int(parts[4])
            if self.command == 'GET':
                row = getattr(db, 'get_' + singular)(row_id)
                if row is None:
                    raise LookupError('Record not found')
                self._reply(200, row)
            elif self.command == 'PUT':
                getattr(db, 'update_' + singular)(row_id, self._body())
                self._reply(200, {'ok': True})
            elif self.command == 'DELETE':
                getattr(db, 'delete_' + singular)(row_id)
                self._reply(200, {'ok': True})
            else:
                raise LookupError('Unknown route')

    def _dispatch(self):
        try:
            self._handle()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except OverflowError:
            self._reply(413, {'error': 'Payload too large'})
        except (ValueError, TypeError, UnicodeError, sqlite3.DataError):
            self._reply(400, {'error': 'Invalid inventory data'})
        except LookupError:
            self._reply(404, {'error': 'Record or route not found'})
        except sqlite3.IntegrityError:
            self._reply(409, {'error': 'Conflicting record or missing parent server'})
        except Exception:
            # Do not log exception text: SQLite errors can embed credential values.
            LOG.error('Inventory request failed; inspect database availability and backup storage.')
            self._reply(500, {'error': 'Inventory operation failed'})

    do_GET = do_POST = do_PUT = do_DELETE = _dispatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', default='inventory.db')
    parser.add_argument('--backup-dir')
    args = parser.parse_args()
    token = os.environ.get('ATLAS_API_TOKEN', '')
    if len(token) < 32:
        parser.error('Set ATLAS_API_TOKEN to a random secret of at least 32 characters.')
    database = DatabaseManager(args.database, seed=False, backup_dir=args.backup_dir,
                               admin_password=os.environ.get('ATLAS_ADMIN_PASSWORD'))
    server = AtlasServer((args.host, args.port), database, token)
    print(f'ATLAS API listening on {args.host}:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
