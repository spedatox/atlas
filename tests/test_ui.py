"""Headless integration checks for the actual Qt storage flows."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QThreadPool
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox, QPushButton
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
        self.widgets = []
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
        self.assertTrue(QThreadPool.globalInstance().waitForDone(5000))
        for widget in reversed(self.widgets):
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(self.errors, [])

    def keep_widget(self, widget):
        self.widgets.append(widget)
        return widget

    def window(self):
        from ui_main import MainWindow
        window = self.keep_widget(MainWindow())
        window.show()
        self.wait_until(lambda: len(window.inventory) == 1)
        return window

    def test_login_and_connection_dialog(self):
        from login import LoginWindow
        from storage_dialogs import BackendDialog
        login = self.keep_widget(LoginWindow())
        login.show()
        login.password_input.setText('atlas2024')
        login._try_login()
        self.wait_until(lambda: login.result() == QDialog.Accepted)
        dialog = self.keep_widget(BackendDialog())
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

    def test_edit_server_profile_then_launch_from_details(self):
        from dialogs import ServerDialog
        from server_profiles import read_details
        window = self.window()
        server = window.inventory[0]
        dialog = ServerDialog(server, window, open_ssh=True)
        self.assertIs(dialog.tabs.currentWidget(), dialog.ssh_editor)
        details = dialog.details_editor
        details.category.setCurrentText('Donanım')
        details.template.setCurrentText('ECC')
        details._add_template()
        details.table.cellWidget(0, 2).setText('Enabled')
        ssh = dialog.ssh_editor
        ssh.auth.setCurrentIndex(ssh.auth.findData('password'))
        ssh.host.setText('test-node.example.net')
        ssh.port.setValue(2222)
        ssh.user.setText('operator')
        ssh.password.setText('ssh-test-only')
        ssh.fingerprint.setText('SHA256:' + 'a' * 43)
        with patch.object(QMessageBox, 'warning', side_effect=AssertionError('Unexpected validation error')):
            dialog._save()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        window._commit_change(lambda: self.db.update_server(server['id'], dialog.result_data))
        self.wait_until(lambda: window.inventory[0].get('ssh_host') == 'test-node.example.net')
        saved = window.inventory[0]
        self.assertEqual(read_details(saved['details_json'])[0]['label'], 'ECC')
        self.assertEqual(saved['password'], 'test-only')
        window._show_server(saved)
        button = next(btn for btn in window.findChildren(QPushButton) if btn.text() == 'SSH Bağlan')
        with patch('ssh_terminal.launch_ssh', return_value=Mock(poll=Mock(return_value=None))) as launch:
            button.click()
        launch.assert_called_once()
        profile, parent = launch.call_args.args
        self.assertEqual((profile.host, profile.port, profile.username), ('test-node.example.net', 2222, 'operator'))
        self.assertEqual(profile.password, 'ssh-test-only')
        self.assertIs(parent, window)

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
            login = self.keep_widget(LoginWindow())
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
