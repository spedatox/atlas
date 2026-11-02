"""Portable inventory backups. Files contain credentials; keep them private."""
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SERVER_COLUMNS = {
    'id': 'INTEGER', 'name': 'TEXT', 'alias': 'TEXT', 'ip_address': 'TEXT',
    'username': 'TEXT', 'password': 'TEXT', 'ram_gb': 'REAL', 'cpu_info': 'TEXT',
    'notes': 'TEXT', 'type': "TEXT DEFAULT 'Server'", 'hostname': 'TEXT',
    'cpu_model': 'TEXT', 'cpu_sockets': 'INTEGER', 'cpu_threads': 'INTEGER',
    'total_ram': 'TEXT', 'system_disk': 'TEXT', 'swap': 'TEXT', 'kernel': 'TEXT',
    'pve_version': 'TEXT', 'boot_mode': 'TEXT', 'storage_pools': 'TEXT',
}
VM_COLUMNS = {
    'id': 'INTEGER', 'server_id': 'INTEGER', 'vm_id': 'INTEGER', 'name': 'TEXT',
    'ip_address': 'TEXT', 'username': 'TEXT', 'password': 'TEXT', 'ram_gb': 'REAL',
    'cores': 'INTEGER', 'disk_info': 'TEXT', 'notes': 'TEXT', 'status': 'TEXT',
    'nic_info': 'TEXT', 'bios_type': 'TEXT', 'machine_type': 'TEXT',
}
MAX_FILE_SIZE = 50 * 1024 * 1024


def make_document(servers, vms):
    return {'format': 'atlas-inventory', 'version': 1,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'servers': servers, 'vms': vms}


def validate_document(document):
    """Validate everything before any database mutation; return normalized rows."""
    if not isinstance(document, dict) or document.get('format') != 'atlas-inventory':
        raise ValueError('ATLAS envanter yedeği bekleniyor.')
    if type(document.get('version')) is not int or document['version'] != 1:
        raise ValueError('Desteklenmeyen yedek sürümü.')
    normalized = {}
    for table, columns in (('servers', SERVER_COLUMNS), ('vms', VM_COLUMNS)):
        rows = document.get(table)
        if not isinstance(rows, list) or len(rows) > 100000:
            raise ValueError(f'Geçersiz kayıt listesi: {table}')
        ids = set()
        normalized[table] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) - set(columns):
                raise ValueError(f'Geçersiz alanlar: {table}')
            if type(row.get('id')) is not int or row['id'] <= 0 or row['id'] in ids:
                raise ValueError(f'Geçersiz veya yinelenen kayıt kimliği: {table}')
            ids.add(row['id'])
            if not isinstance(row.get('name'), str) or not row['name'].strip():
                raise ValueError('Kayıt adı boş olamaz.')
            clean = {}
            for key, sql_type in columns.items():
                value = row.get(key)
                if key == 'type' and value is None:
                    value = 'Server'
                if value is not None:
                    if sql_type.startswith('TEXT') and not isinstance(value, str):
                        raise ValueError(f'Metin bekleniyor: {table}.{key}')
                    if sql_type == 'INTEGER' and (type(value) is not int or abs(value) > 2**63 - 1):
                        raise ValueError(f'Tamsayı bekleniyor: {table}.{key}')
                    if sql_type == 'REAL' and (type(value) not in (int, float) or not math.isfinite(value)):
                        raise ValueError(f'Sayı bekleniyor: {table}.{key}')
                clean[key] = value
            if table == 'servers' and clean['type'] not in ('Server', 'Storage'):
                raise ValueError('Bilinmeyen sunucu türü.')
            normalized[table].append(clean)
    server_ids = {s['id'] for s in normalized['servers']}
    names = [s['name'] for s in normalized['servers']]
    if len(names) != len(set(names)):
        raise ValueError('Sunucu adları benzersiz olmalı.')
    for vm in normalized['vms']:
        if vm['server_id'] not in server_ids:
            raise ValueError('VM için geçerli bir üst sunucu bulunamadı.')
    return make_document(normalized['servers'], normalized['vms'])


def read_document(path):
    path = Path(path).resolve()
    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError('Yedek dosyası 50 MiB sınırını aşıyor.')
    with path.open('rb') as source:
        sqlite_file = source.read(16) == b'SQLite format 3\x00'
    if sqlite_file:
        # Read-only mode never initializes, migrates, or executes SQL from the file.
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite yedeği bozuk.')
            rows = {}
            for table, columns in (('servers', SERVER_COLUMNS), ('vms', VM_COLUMNS)):
                kind = conn.execute('SELECT type FROM sqlite_master WHERE name=?', (table,)).fetchone()
                if not kind or kind[0] != 'table':
                    raise ValueError(f'ATLAS tablosu bulunamadı: {table}')
                present = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
                required = {'id', 'name'} | ({'server_id'} if table == 'vms' else set())
                if not required <= present:
                    raise ValueError(f'ATLAS alanları bulunamadı: {table}')
                fields = ','.join(c for c in columns if c in present)
                rows[table] = [dict(r) for r in conn.execute(f'SELECT {fields} FROM {table} LIMIT 100001')]
            return validate_document(make_document(rows['servers'], rows['vms']))
    with path.open(encoding='utf-8-sig') as source:
        return validate_document(json.load(source))


def write_document(path, document):
    """Atomic replacement leaves an existing backup intact on write failure."""
    path = Path(path).resolve()
    fd, temporary = tempfile.mkstemp(prefix='.atlas-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(document, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
