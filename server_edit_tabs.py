import json
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from server_profiles import SSH_COLUMNS, SshProfile, read_details, ssh_hostname, validate_details


# Templates are suggestions. Operators can name categories and fields for any component.
DETAIL_TEMPLATES = {
    'Kimlik ve konum': (
        'Envanter numarası', 'Üretici', 'Model', 'Seri numarası', 'Varlık etiketi', 'Cihaz rolü',
        'Ortam', 'Durum', 'Kurum / departman', 'Sorumlu ekip', 'Birincil irtibat', 'Etiketler',
        'Site / veri merkezi', 'Oda', 'Raf', 'Raf konumu (U)', 'Şasi tipi',
    ),
    'Donanım': (
        'Anakart', 'İşlemci mimarisi', 'CPU çekirdeği', 'CPU frekansı', 'RAM türü', 'RAM hızı',
        'DIMM yuvaları', 'ECC', 'GPU / hızlandırıcı', 'PCIe yuvaları', 'HBA', 'RAID denetleyicisi',
        'BIOS / UEFI sürümü', 'TPM', 'Secure Boot', 'Donanım yazılımı', 'Sensörler',
    ),
    'Depolama': (
        'Disk envanteri', 'Disk yuvaları', 'Disk arabirimi', 'RAID seviyesi', 'Ham kapasite',
        'Kullanılabilir kapasite', 'Dosya sistemi', 'Bağlama noktaları', 'Şifreleme', 'SMART durumu',
        'Paylaşımlar ve dışa aktarımlar', 'Anlık görüntü politikası', 'Replikasyon',
    ),
    'Ağ': (
        'FQDN', 'IPv4 / CIDR', 'IPv6 / CIDR', 'Ağ geçidi', 'DNS sunucuları', 'Arama alanı',
        'NTP sunucuları', 'Ağ arabirimleri', 'MAC adresleri', 'VLAN', 'MTU', 'Bond / köprü',
        'Switch ve port', 'Genel IP / NAT', 'Güvenlik duvarı bölgesi', 'Açık portlar', 'VPN / bastion',
    ),
    'Yazılım ve hizmetler': (
        'İşletim sistemi', 'Sürüm / dağıtım', 'Hipervizör', 'Küme', 'Küme düğümü',
        'Çalışan hizmetler', 'Uygulama sürümleri', 'Konteyner çalışma zamanı', 'Bağımlılıklar',
        'Lisans', 'Konfigürasyon deposu', 'Dağıtım yöntemi', 'Yama düzeyi', 'Son güncelleme',
    ),
    'Yönetim ve güvenlik': (
        'Yönetim URL’si', 'Yönetim IP adresi', 'BMC türü (IPMI / iLO / iDRAC)', 'BMC sürümü',
        'Konsol / KVM', 'Erişim grubu', 'Kimlik sağlayıcısı', 'Sertifika bitişi',
        'Sertifika otoritesi', 'Güvenlik sınıfı', 'Son güvenlik taraması', 'Sır kasası referansı',
    ),
    'İşletim ve kurtarma': (
        'İzleme adresi', 'Alarm irtibatı', 'Log hedefi', 'Bakım penceresi', 'Son bakım',
        'Son denetim', 'Yedek hedefi', 'Yedek takvimi', 'Yedek saklama süresi', 'Son başarılı yedek',
        'Son geri yükleme testi', 'RPO', 'RTO', 'Felaket kurtarma planı', 'Runbook', 'Olay / iş kaydı',
    ),
    'Güç ve yaşam döngüsü': (
        'Güç kaynakları', 'Güç tüketimi', 'UPS', 'PDU / priz', 'Satın alma tarihi', 'Tedarikçi',
        'Sipariş / sözleşme numarası', 'Garanti bitişi', 'Destek bitişi', 'Destek irtibatı',
        'Hizmete alma tarihi', 'Değiştirme planı', 'Hizmetten çıkarma tarihi',
    ),
}


def _input(value='', placeholder=''):
    editor = QLineEdit(value or '')
    editor.setPlaceholderText(placeholder)
    editor.setObjectName('dlgInput')
    editor.setMinimumHeight(30)
    return editor


class ServerDetailsEditor(QWidget):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        tip = QLabel('Hazır alanları seçin veya kendi alanınızı ekleyin. Aynı türden birden fazla bileşen için '
                     'ayrı kategoriler kullanın (ör. Disk 1, Disk 2). Gizli alanlar ekranda maskelenir.')
        tip.setWordWrap(True)
        layout.addWidget(tip)

        controls = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItems(['Özel', *DETAIL_TEMPLATES])
        self.category.currentTextChanged.connect(self._update_templates)
        controls.addWidget(self.category)
        self.template = QComboBox()
        self._update_templates(self.category.currentText())
        controls.addWidget(self.template, 1)
        add = QPushButton('Alan Ekle')
        add.clicked.connect(self._add_template)
        controls.addWidget(add)
        remove = QPushButton('Seçili Alanı Kaldır')
        remove.clicked.connect(self._remove_selection)
        controls.addWidget(remove)
        layout.addLayout(controls)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Kategori', 'Alan Adı', 'Değer', 'Gizli'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 160)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table, 1)
        for row in read_details(server.get('details_json')):
            self._add_row(row['category'], row['label'], row['value'], row['secret'])

    def _add_row(self, category, label, value='', secret=False):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(category))
        self.table.setItem(row, 1, QTableWidgetItem(label))
        editor = _input(value, 'Değer girin')
        editor.setMaxLength(16000)
        self.table.setCellWidget(row, 2, editor)
        checkbox = QCheckBox()
        checkbox.toggled.connect(lambda checked: editor.setEchoMode(
            QLineEdit.EchoMode.Password if checked else QLineEdit.EchoMode.Normal))
        checkbox.setChecked(secret)
        self.table.setCellWidget(row, 3, checkbox)
        return row

    def _update_templates(self, category):
        self.template.clear()
        self.template.addItem('Özel alan', '')
        for label in DETAIL_TEMPLATES.get(category, ()):
            self.template.addItem(label, label)

    def _add_template(self):
        category = self.category.currentText()
        label = self.template.currentData()
        row = self._add_row(category, label)
        self.table.setCurrentCell(row, 2 if label else 1)
        if label:
            self.table.cellWidget(row, 2).setFocus()
        else:
            self.table.editItem(self.table.item(row, 1))

    def _remove_selection(self):
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def serialized(self):
        rows = []
        for index in range(self.table.rowCount()):
            value = self.table.cellWidget(index, 2).text()
            if value.strip():
                rows.append({'category': self.table.item(index, 0).text().strip(),
                             'label': self.table.item(index, 1).text().strip(),
                             'value': value, 'secret': self.table.cellWidget(index, 3).isChecked()})
        validate_details(rows)
        return json.dumps(rows, ensure_ascii=False) if rows else None


def _suggest_host(server):
    for key in ('ip_address', 'name', 'hostname'):
        value = server.get(key) or ''
        try:
            return ssh_hostname(value)
        except ValueError:
            try:
                address = value if '://' in value else '//' + value
                return ssh_hostname(urlsplit(address).hostname or '')
            except ValueError:
                pass
    return ''


class SshProfileEditor(QWidget):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        form = QFormLayout()
        self.auth = QComboBox()
        self.auth.setObjectName('dlgCombo')
        self.auth.setMinimumHeight(34)
        self.auth.addItem('Devre dışı', None)
        self.auth.addItem('OpenSSH · anahtar / etkileşimli giriş', 'openssh')
        self.auth.addItem('Plink · kayıtlı parola', 'password')
        self.auth.setCurrentIndex(max(0, self.auth.findData(server.get('ssh_auth'))))
        self.host = _input(server.get('ssh_host'), 'sunucu.example.net')
        self.port = QSpinBox()
        self.port.setObjectName('dlgSpin')
        self.port.setMinimumHeight(30)
        self.port.setRange(1, 65535)
        self.port.setValue(server.get('ssh_port') or 22)
        self.user = _input(server.get('ssh_username'), 'SSH kullanıcı adı')
        self.password = _input(server.get('ssh_password'), 'SSH parolası')
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.fingerprint = _input(server.get('ssh_fingerprint'), 'SHA256:…')
        self.key = _input(server.get('ssh_key_path'), 'İsteğe bağlı · yerel anahtar dosyası')
        self.browse = QPushButton('Seç…')
        self.browse.clicked.connect(self._browse_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key)
        key_row.addWidget(self.browse)
        form.addRow('Kimlik doğrulama', self.auth)
        form.addRow('SSH sunucusu', self.host)
        form.addRow('SSH portu', self.port)
        form.addRow('SSH kullanıcısı', self.user)
        form.addRow('SSH parolası', self.password)
        form.addRow('Sunucu anahtar izi', self.fingerprint)
        form.addRow('Özel anahtar yolu', key_row)
        layout.addLayout(form)

        help_text = QLabel('Kayıtlı parola modu PuTTY Plink ve güvenilir bir kaynaktan doğrulanmış SHA256 '
                           'sunucu anahtar izi gerektirir. OpenSSH modu yerel SSH anahtarlarını, aracıyı ve '
                           'etkileşimli parola girişini destekler. SSH parolası envanter ve yedeklere kaydedilir.')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        layout.addStretch()
        self.auth.currentIndexChanged.connect(self._update_inputs)
        self.suggest_defaults(server)
        self._update_inputs()

    def suggest_defaults(self, server):
        if not self.host.text():
            self.host.setText(_suggest_host(server))
        if not self.user.text():
            self.user.setText(server.get('username') or '')

    def _update_inputs(self):
        mode = self.auth.currentData()
        for widget in (self.host, self.port, self.user):
            widget.setEnabled(mode is not None)
        self.password.setEnabled(mode == 'password')
        self.fingerprint.setEnabled(mode == 'password')
        self.key.setEnabled(mode == 'openssh')
        self.browse.setEnabled(mode == 'openssh')

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Yerel OpenSSH Özel Anahtarı Seç')
        if path:
            self.key.setText(path)

    def values(self):
        auth = self.auth.currentData()
        if auth is None:
            return dict.fromkeys(SSH_COLUMNS)
        values = {'ssh_auth': auth, 'ssh_host': self.host.text().strip(),
                  'ssh_port': self.port.value(), 'ssh_username': self.user.text().strip(),
                  'ssh_password': self.password.text() if auth == 'password' else None,
                  'ssh_fingerprint': self.fingerprint.text().strip() if auth == 'password' else None,
                  'ssh_key_path': (self.key.text().strip() or None) if auth == 'openssh' else None}
        SshProfile.from_record(values)
        return values
