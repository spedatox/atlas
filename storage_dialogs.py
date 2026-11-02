"""Data source settings and import preview for ATLAS."""
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                               QLineEdit, QLabel, QDialogButtonBox, QPushButton,
                               QMessageBox)
from backends import BackendProxy, RemoteBackend, db_manager, load_settings, save_settings
from tasks import run_task


class BackendDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Veri Kaynağı')
        self.setObjectName('atlasDialog')
        self.setMinimumWidth(560)
        settings = load_settings()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem('Yerel SQLite', 'local')
        self.mode.addItem('Uzak ATLAS sunucusu', 'remote')
        self.mode.setObjectName('dlgCombo')
        self.mode.setMinimumHeight(34)
        self.mode.setCurrentIndex(1 if settings['backend'] == 'remote' else 0)
        self.url = QLineEdit(settings['url'])
        self.url.setPlaceholderText('https://atlas.example.com')
        self.token = QLineEdit(os.environ.get('ATLAS_API_TOKEN', ''))
        if isinstance(db_manager._backend, RemoteBackend):
            self.token.setText(db_manager._backend._token)
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText('API anahtarı (yalnızca bu oturumda tutulur)')
        for field in (self.url, self.token):
            field.setObjectName('dlgInput')
            field.setMinimumHeight(34)
        form.addRow('Veri kaynağı', self.mode)
        form.addRow('Sunucu adresi', self.url)
        form.addRow('API anahtarı', self.token)
        layout.addLayout(form)
        note = QLabel('Yerel ve uzak envanterler ayrıdır. Veri taşımak için yedek alıp içe aktarın.\n'
                      'API anahtarı diske kaydedilmez; kalıcı kullanım için ATLAS_API_TOKEN ayarlayın.')
        note.setWordWrap(True)
        layout.addWidget(note)
        if any(os.environ.get(k) for k in ('ATLAS_BACKEND', 'ATLAS_REMOTE_URL')):
            env = QLabel('Başlangıçta ortam değişkenleri kayıtlı veri kaynağı ayarlarının önüne geçer.')
            env.setWordWrap(True)
            layout.addWidget(env)
        self.test = QPushButton('Bağlantıyı Test Et')
        self.test.clicked.connect(self._test)
        layout.addWidget(self.test)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('Kaydet')
        buttons.button(QDialogButtonBox.Cancel).setText('İptal')
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self._toggle)
        self._toggle()

    def _toggle(self):
        remote = self.mode.currentData() == 'remote'
        for widget in (self.url, self.token, self.test):
            widget.setEnabled(remote)

    def _error(self, message):
        QMessageBox.critical(self, 'Bağlantı Hatası', message)

    def _test(self):
        url, token = self.url.text(), self.token.text()
        run_task(self, 'Bağlantı kontrol ediliyor...',
                 lambda: RemoteBackend(url, token).check_connection(),
                 lambda _: QMessageBox.information(self, 'Bağlantı', 'ATLAS sunucusuna bağlanıldı.'), self._error)

    def _save(self):
        settings = {'backend': self.mode.currentData(), 'url': self.url.text().strip().rstrip('/')}
        token = self.token.text()

        def configure():
            candidate = BackendProxy()
            candidate.configure(settings, token)
            save_settings(settings)
            return candidate

        def apply(candidate):
            db_manager._backend, db_manager.mode = candidate._backend, candidate.mode
            self.accept()

        run_task(self, 'Veri kaynağı hazırlanıyor...', configure, apply, self._error)


class ImportDialog(QDialog):
    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Envanter İçe Aktar')
        self.setObjectName('atlasDialog')
        self.setMinimumWidth(530)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel(f"Yedek: {len(document['servers'])} sunucu / depolama, {len(document['vms'])} VM"))
        target = 'Uzak sunucu' if db_manager.mode == 'remote' else 'Yerel veritabanı'
        location = db_manager.url if db_manager.mode == 'remote' else db_manager.db_path
        destination = QLabel(f'Hedef: {target}\n{location}')
        destination.setWordWrap(True)
        layout.addWidget(destination)
        self.mode = QComboBox()
        self.mode.setObjectName('dlgCombo')
        self.mode.setMinimumHeight(34)
        self.mode.addItem('Birleştir — mevcut kayıtları koru', 'merge')
        self.mode.addItem('Değiştir — tüm envanteri yedekteki kayıtlarla değiştir', 'replace')
        layout.addWidget(self.mode)
        note = QLabel('Birleştirme: sunucular adlarına göre, VM’ler sunucu + VM ID ile eşleştirilir. '
                      'VM ID yoksa ad kullanılır. Eşleşen kayıtlar değiştirilmez.\n\n'
                      'İşlem öncesi otomatik kurtarma yedeği alınır. Giriş kullanıcıları korunur.')
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('İçe Aktar')
        buttons.button(QDialogButtonBox.Cancel).setText('İptal')
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _confirm(self):
        if self.mode.currentData() == 'replace':
            reply = QMessageBox.warning(self, 'Tüm Envanteri Değiştir',
                                        'Hedefteki tüm sunucu ve VM kayıtları değiştirilecek. Devam edilsin mi?',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.accept()
