import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from backends import BackendError, BackendProxy, RemoteBackend, normalize_url, save_settings
from database import DatabaseManager
from inventory_io import make_document, read_document, write_document
from server import AtlasServer


def sample():
    return make_document(
        [{'id': 40, 'name': 'node-ü', 'alias': 'Sunucu', 'password': 'test-only',
          'ram_gb': 128, 'cpu_info': 'test CPU', 'type': 'Server'},
         {'id': 80, 'name': 'nas', 'type': 'Storage'}],
        [{'id': 99, 'server_id': 40, 'vm_id': 101, 'name': 'test-vm',
          'password': 'test-vm-only', 'notes': 'Unicode: çğıöşü', 'ram_gb': 2.5}])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = DatabaseManager(self.root / 'inventory.db', seed=False)

    def test_roundtrip_json_and_sqlite_preserves_all_fields_and_users(self):
        self.db.import_document(sample(), 'replace')
        exported = self.root / 'backup.json'
        self.db.export_backup(exported)
        original = self.db.export_document()
        for path in (exported, Path(self.db.create_backup())):
            other = DatabaseManager(self.root / ('copy-' + path.suffix[1:] + '.db'), seed=False)
            other.import_file(path, 'replace')
            self.assertEqual(other.get_inventory(), self.db.get_inventory())
            self.assertTrue(other.authenticate('admin', 'atlas2024'))
        self.assertEqual(read_document(exported)['servers'], original['servers'])
        self.assertNotIn('users', json.loads(exported.read_text(encoding='utf-8')))

    def test_merge_is_idempotent_and_preserves_existing_values(self):
        self.db.import_document(sample())
        doc = sample()
        doc['servers'][0]['password'] = 'must-not-overwrite'
        doc['vms'][0]['notes'] = 'must-not-overwrite'
        doc['vms'].append({'id': 100, 'server_id': 40, 'name': 'second', 'vm_id': None})
        result = self.db.import_document(doc)
        self.assertEqual(result['servers_skipped'], 2)
        self.assertEqual(result['vms_skipped'], 1)
        self.assertEqual(result['vms_added'], 1)
        self.assertEqual(self.db.import_document(doc)['vms_added'], 0)
        server = next(s for s in self.db.get_inventory() if s['name'] == 'node-ü')
        self.assertEqual(server['password'], 'test-only')
        vm = next(vm for vm in server['vms'] if vm['vm_id'] == 101)
        self.assertEqual(vm['notes'], 'Unicode: çğıöşü')

    def test_replace_preserves_duplicates_and_remaps_relationships(self):
        self.db.add_server({'name': 'unrelated'})
        doc = sample()
        doc['vms'].append(dict(doc['vms'][0], id=100))
        result = self.db.import_document(doc, 'replace')
        self.assertEqual(result['vms_added'], 2)
        self.assertEqual(len(self.db.get_inventory()), 2)
        old = read_document(result['backup_path'])
        self.assertEqual([s['name'] for s in old['servers']], ['unrelated'])

    def test_invalid_documents_leave_database_unchanged(self):
        self.db.import_document(sample())
        before = self.db.get_inventory()
        cases = []
        for key, value in (('version', 2), ('servers', None), ('format', 'wrong')):
            doc = sample()
            doc[key] = value
            cases.append(doc)
        doc = sample()
        doc['vms'][0]['server_id'] = 12345
        cases.append(doc)
        doc = sample()
        doc['servers'].append(doc['servers'][0])
        cases.append(doc)
        doc = sample()
        doc['vms'][0]['ram_gb'] = float('nan')
        cases.append(doc)
        doc = sample()
        doc['servers'][0]['id'] = True
        cases.append(doc)
        for doc in cases:
            with self.subTest(document=doc), self.assertRaises(ValueError):
                self.db.import_document(doc, 'replace')
            self.assertEqual(before, self.db.get_inventory())

    def test_sql_failure_rolls_back_replace_and_keeps_recovery_copy(self):
        self.db.import_document(sample())
        before = self.db.get_inventory()
        with patch.object(self.db, '_insert_row', side_effect=sqlite3.IntegrityError('injected')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.import_document(sample(), 'replace')
        self.assertEqual(before, self.db.get_inventory())
        self.assertEqual(len(list(self.db.backup_dir.glob('*.db'))), 2)

    def test_backup_failure_prevents_import(self):
        self.db.add_server({'name': 'keep'})
        with patch.object(self.db, 'create_backup', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.db.import_document(sample(), 'replace')
        self.assertEqual(self.db.get_inventory()[0]['name'], 'keep')

    def test_backup_is_consistent_in_wal_mode(self):
        with closing(self.db.get_connection()) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            self.db.import_document(sample())
            snapshot = self.db.create_backup()
            self.assertEqual(len(read_document(snapshot)['vms']), 1)
            with closing(sqlite3.connect(snapshot)) as saved:
                self.assertEqual(saved.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_cannot_overwrite_active_database(self):
        for method in (self.db.create_backup, self.db.export_backup):
            with self.assertRaises(ValueError):
                method(self.db.db_path)
            with self.assertRaises(ValueError):
                method(self.db.db_path + '-wal')

    def test_legacy_migration_preserves_inventory_and_creates_snapshot(self):
        path = self.root / 'legacy.db'
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute('CREATE TABLE servers (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL)')
            conn.execute("INSERT INTO servers VALUES (7, 'legacy')")
            conn.execute('CREATE TABLE vms (id INTEGER PRIMARY KEY, server_id INTEGER, name TEXT NOT NULL)')
            conn.execute("INSERT INTO vms VALUES (9, 7, 'old-vm')")
        db = DatabaseManager(path, seed=False)
        self.assertEqual(db.get_server(7)['name'], 'legacy')
        self.assertEqual(db.get_vm(9)['name'], 'old-vm')
        backups = list(db.backup_dir.glob('startup-*.db'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as old:
            self.assertNotIn('alias', [r[1] for r in old.execute('PRAGMA table_info(servers)')])
        DatabaseManager(path, seed=False)
        self.assertEqual(len(list(db.backup_dir.glob('startup-*.db'))), 1)

    def test_unrelated_or_corrupt_database_is_rejected(self):
        path = self.root / 'other.db'
        with closing(sqlite3.connect(path)) as conn:
            conn.execute('CREATE TABLE unrelated (value TEXT)')
        with self.assertRaises(ValueError):
            read_document(path)
        path.write_bytes(b'SQLite format 3\x00broken')
        with self.assertRaises(sqlite3.DatabaseError):
            read_document(path)

    def test_foreign_keys_enforced_and_failed_writes_release_locks(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_vm({'name': 'orphan', 'server_id': 123})
        self.db.add_server({'name': 'valid'})
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_server({'name': 'valid'})
        self.db.add_server({'name': 'also-valid'})

    def test_update_preserves_unspecified_fields(self):
        sid = self.db.add_server({'name': 'node', 'ram_gb': 64, 'cpu_info': 'CPU'})
        self.db.update_server(sid, {'name': 'renamed'})
        row = self.db.get_server(sid)
        self.assertEqual(row['ram_gb'], 64)
        self.assertEqual(row['cpu_info'], 'CPU')
        with self.assertRaises(LookupError):
            self.db.update_server(999, {'name': 'missing'})

    def test_server_database_requires_explicit_initial_password(self):
        with self.assertRaises(ValueError):
            DatabaseManager(self.root / 'remote.db', seed=False, admin_password=None)


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = DatabaseManager(self.root / 'remote.db', seed=False, admin_password='private-test')
        self.token = 'test-token-' + 'a' * 32
        self.server = AtlasServer(('127.0.0.1', 0), self.db, self.token)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.client = RemoteBackend(self.url, self.token, timeout=2)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def login(self):
        self.assertTrue(self.client.authenticate('admin', 'private-test'))

    def test_authentication_and_session_are_required(self):
        self.assertEqual(self.client.check_connection()['service'], 'atlas')
        with self.assertRaises(BackendError):
            RemoteBackend(self.url, 'incorrect').check_connection()
        with self.assertRaises(BackendError):
            self.client.get_inventory()
        self.assertFalse(self.client.authenticate('admin', 'wrong'))
        self.login()
        self.server.sessions[self.client._session] = 0
        with self.assertRaises(BackendError):
            self.client.get_inventory()

    def test_remote_crud_and_shared_inventory(self):
        self.login()
        sid = self.client.add_server({'name': 'remote-node'})
        vid = self.client.add_vm({'name': 'remote-vm', 'server_id': sid, 'vm_id': 101})
        self.client.update_server(sid, {'alias': 'Updated'})
        self.client.update_vm(vid, {'notes': 'Changed'})
        self.assertEqual(self.client.get_server(sid)['alias'], 'Updated')
        self.assertEqual(self.client.get_vm(vid)['notes'], 'Changed')
        second = RemoteBackend(self.url, self.token)
        self.assertTrue(second.authenticate('admin', 'private-test'))
        self.assertEqual(len(second.get_inventory()[0]['vms']), 1)
        self.client.delete_vm(vid)
        self.client.delete_server(sid)
        self.assertEqual(second.get_inventory(), [])

    def test_remote_import_export_and_server_side_recovery(self):
        self.login()
        source = self.root / 'source.json'
        write_document(source, sample())
        result = self.client.import_file(source, 'replace')
        self.assertTrue(Path(result['backup_path']).is_file())
        self.assertEqual(result['vms_added'], 1)
        exported = self.root / 'remote-backup.json'
        self.client.export_backup(exported)
        self.assertEqual(len(read_document(exported)['servers']), 2)
        self.assertTrue(Path(self.client.create_backup()).exists())
        self.assertTrue(self.db.authenticate('admin', 'private-test'))

    def test_bad_requests_missing_records_and_integrity_errors(self):
        self.login()
        with self.assertRaises(BackendError):
            self.client.add_server({'name': 'bad', 'unexpected': 'value'})
        with self.assertRaises(BackendError):
            self.client.add_vm({'name': 'orphan', 'server_id': 99})
        with self.assertRaises(BackendError):
            self.client.get_server(999)
        with self.assertRaises(BackendError):
            self.client.delete_vm(999)
        self.assertEqual(self.client.get_inventory(), [])

    def test_no_silent_local_fallback(self):
        proxy = BackendProxy()
        proxy.configure({'backend': 'remote', 'url': self.url}, self.token)
        self.assertEqual(proxy.mode, 'remote')
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaises(BackendError):
            proxy.authenticate('admin', 'private-test')
        self.assertEqual(proxy.mode, 'remote')
        self.assertIsInstance(proxy._backend, RemoteBackend)

    def test_settings_never_store_secrets(self):
        config = self.root / 'config.json'
        with patch.dict(os.environ, {'ATLAS_CONFIG_PATH': str(config)}):
            save_settings({'backend': 'remote', 'url': self.url, 'token': 'do-not-save'})
        self.assertNotIn('do-not-save', config.read_text())
        self.assertNotIn('token', config.read_text())

    def test_login_rate_limit(self):
        for _ in range(20):
            self.assertFalse(self.client.authenticate('admin', 'wrong'))
        with self.assertRaisesRegex(BackendError, 'bir dakika'):
            self.client.authenticate('admin', 'wrong')

    def test_https_required_for_remote_hosts(self):
        for url in ('http://example.com', 'https://user:secret@example.com', 'https://example.com#token', 'file:///tmp'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_url(url)
        self.assertEqual(normalize_url(' https://example.com/atlas/ '), 'https://example.com/atlas')

    def test_redirect_does_not_forward_credentials(self):
        received = []

        class Redirect(BaseHTTPRequestHandler):
            def do_GET(handler):
                if handler.path == '/destination':
                    received.append(handler.headers.get('Authorization'))
                handler.send_response(302)
                handler.send_header('Location', '/destination')
                handler.end_headers()

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = RemoteBackend(f'http://127.0.0.1:{server.server_port}', self.token)
            with self.assertRaises(BackendError):
                client.check_connection()
            self.assertEqual(received, [])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
