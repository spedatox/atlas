"""Shared validation for server details and SSH profiles."""
import ipaddress
import json
import re
from dataclasses import dataclass, field


SSH_COLUMNS = {
    'ssh_auth': 'TEXT', 'ssh_host': 'TEXT', 'ssh_port': 'INTEGER',
    'ssh_username': 'TEXT', 'ssh_password': 'TEXT', 'ssh_fingerprint': 'TEXT',
    'ssh_key_path': 'TEXT',
}


def validate_details(rows):
    if not isinstance(rows, list) or len(rows) > 512:
        raise ValueError('En fazla 512 sunucu ayrıntısı kaydedilebilir.')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'category', 'label', 'value', 'secret'}:
            raise ValueError('Geçersiz sunucu ayrıntısı.')
        for key, limit in (('category', 128), ('label', 128), ('value', 16000)):
            value = row[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
                raise ValueError('Ayrıntıların kategorisi, adı ve değeri geçerli olmalı.')
        if type(row['secret']) is not bool:
            raise ValueError('Geçersiz gizli alan seçimi.')
        key = (row['category'].strip().casefold(), row['label'].strip().casefold())
        if key in seen:
            raise ValueError('Aynı kategoride bir alan adı yalnızca bir kez kullanılabilir.')
        seen.add(key)
    return rows


def read_details(value):
    return validate_details(json.loads(value)) if value is not None else []


def ssh_hostname(value):
    host = value.strip()
    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]
    if '%' in host and not re.fullmatch(r'[a-zA-Z0-9_.-]+', host.rsplit('%', 1)[1]):
        raise ValueError('IPv6 kapsam kimliği geçerli olmalı.')
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        host = host.encode('idna').decode('ascii')
    except UnicodeError:
        host = ''
    labels = host.rstrip('.').split('.')
    if len(host) > 254 or not all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
                                  for label in labels):
        raise ValueError('SSH için geçerli bir IP adresi veya ana bilgisayar adı girin. Portu ayrı girin.')
    return host


@dataclass(frozen=True)
class SshProfile:
    auth: str
    host: str
    port: int
    username: str
    password: str = field(default='', repr=False)
    fingerprint: str = ''
    key_path: str = ''

    @classmethod
    def from_record(cls, record):
        auth = record.get('ssh_auth')
        if auth is None:
            return None
        if auth not in ('openssh', 'password'):
            raise ValueError('Bilinmeyen SSH kimlik doğrulama yöntemi.')
        host = ssh_hostname(record.get('ssh_host') or '')
        port = record.get('ssh_port')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('SSH portu 1–65535 arasında olmalı.')
        user = (record.get('ssh_username') or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@+\\$-]{0,127}', user):
            raise ValueError('SSH kullanıcı adı geçerli olmalı.')
        if auth == 'openssh':
            return cls(auth, host, port, user, key_path=(record.get('ssh_key_path') or '').strip())

        password = record.get('ssh_password') or ''
        if not password or any(char in password for char in '\r\n\x00') or len(password.encode('utf-8')) > 4096:
            raise ValueError('SSH parolası boş olamaz, satır sonu içeremez ve en fazla 4096 bayt olabilir.')
        fingerprint = (record.get('ssh_fingerprint') or '').strip().rstrip('=')
        if not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}', fingerprint):
            raise ValueError('Doğrulanmış SSH ana bilgisayar parmak izini SHA256:… biçiminde girin.')
        return cls(auth, host, port, user, password=password, fingerprint=fingerprint)
