"""Headless integration checks for the actual Qt storage flows."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtCore import QThreadPool, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.app.setStyleSheet((Path(__file__).parents[1] / 'styles.qss').read_text(encoding='utf-8'))

    def setUp(self):
        from backends import db_manager
        from database import DatabaseManager
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = DatabaseManager(self.root / 'ui.db', seed=False)
        self.db.add_server({'name': 'UI node', 'alias': 'Test', 'password': 'test-only'})
        db_manager._backend = self.db
        db_manager.mode = 'local'
        self.environment = patch.dict(os.environ, {'ATLAS_CONFIG_PATH': str(self.root / 'settings.json')})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.errors = []
        self.messages = []
        for name, values in (('critical', self.errors), ('information', self.messages)):
            mock = patch.object(QMessageBox, name, side_effect=lambda *args, values=values: values.append(args[2]))
            mock.start()
            self.addCleanup(mock.stop)

    def wait_until(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            QTest.qWait(10)
        self.fail(f'UI operation did not finish. Errors: {self.errors}')

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        for widget in QApplication.topLevelWidgets():
            widget.close()
        self.app.processEvents()
        self.assertEqual(self.errors, [])

    def window(self):
        from ui_main import MainWindow
        window = MainWindow()
        window.show()
        self.wait_until(lambda: len(window.inventory) == 1)
        return window

    def test_login_and_connection_dialog(self):
        from login import LoginWindow
        from storage_dialogs import BackendDialog
        login = LoginWindow()
        login.show()
        login.password_input.setText('atlas2024')
        login._try_login()
        self.wait_until(lambda: login.result() == QDialog.Accepted)
        dialog = BackendDialog()
        self.assertFalse(dialog.url.isEnabled())
        dialog.mode.setCurrentIndex(1)
        self.assertTrue(dialog.url.isEnabled())

    def test_backup_menu_writes_portable_and_full_backups(self):
        from inventory_io import read_document
        window = self.window()
        for extension, selected in (('json', 'ATLAS JSON (*.json)'), ('db', 'Tam SQLite Yedeği (*.db)')):
            path = self.root / f'backup.{extension}'
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(path), selected)):
                window._backup_inventory()
                self.wait_until(lambda: path.exists())
                self.wait_until(lambda: len(self.messages) >= (1 if extension == 'json' else 2))
            self.assertEqual(read_document(path)['servers'][0]['name'], 'UI node')

    def test_import_preview_merge_and_refresh(self):
        from inventory_io import make_document, write_document
        from storage_dialogs import ImportDialog
        window = self.window()
        path = self.root / 'new.json'
        write_document(path, make_document([{'id': 1, 'name': 'Imported node'}], []))
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(path), '')), \
                patch.object(ImportDialog, 'exec', return_value=QDialog.Accepted):
            window._import_inventory()
            self.wait_until(lambda: len(window.inventory) == 2)
        self.assertTrue(any('Kurtarma' in msg for msg in self.messages))

    def test_refresh_and_edits_update_visible_details(self):
        window = self.window()
        window._show_server(window.inventory[0])
        sid = window.inventory[0]['id']
        window._commit_change(lambda: self.db.update_server(sid, {'alias': 'Changed'}))
        self.wait_until(lambda: window._current_server['alias'] == 'Changed')
        window._commit_change(lambda: self.db.delete_server(sid))
        self.wait_until(lambda: not window.inventory)
        self.assertIsNone(window._current_server)

    def test_remote_login_and_inventory_in_desktop(self):
        from backends import db_manager, RemoteBackend
        from login import LoginWindow
        from server import AtlasServer
        server = AtlasServer(('127.0.0.1', 0), self.db, 'ui-test-' + 'a' * 32)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            db_manager._backend = RemoteBackend(f'http://127.0.0.1:{server.server_port}', server.token)
            db_manager.mode = 'remote'
            login = LoginWindow()
            login.show()
            login.password_input.setText('atlas2024')
            login._try_login()
            self.wait_until(lambda: login.result() == QDialog.Accepted)
            window = self.window()
            self.assertIn('Uzak sunucu', window.statusBar().currentMessage())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
