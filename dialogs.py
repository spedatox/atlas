from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QPushButton, QFrame, QScrollArea,
    QWidget, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def _section_title(text):
    lbl = QLabel(text)
    lbl.setObjectName("dlgSectionTitle")
    return lbl


def _separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setObjectName("dlgSeparator")
    return sep


class _FormField(QWidget):
    """Label + input pair for dialog forms."""
    def __init__(self, label, widget, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(12)
        lbl = QLabel(label)
        lbl.setObjectName("dlgFieldLabel")
        lbl.setFixedWidth(140)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lbl)
        lay.addWidget(widget, 1)
        self.widget = widget


def _line(placeholder='', value='', read_only=False):
    w = QLineEdit()
    w.setObjectName("dlgInput")
    w.setFixedHeight(34)
    if placeholder:
        w.setPlaceholderText(placeholder)
    if value:
        w.setText(str(value))
    if read_only:
        w.setReadOnly(True)
    return w


def _text(placeholder='', value=''):
    w = QTextEdit()
    w.setObjectName("dlgTextArea")
    w.setFixedHeight(70)
    if placeholder:
        w.setPlaceholderText(placeholder)
    if value:
        w.setPlainText(str(value))
    return w


def _combo(options, current=None):
    w = QComboBox()
    w.setObjectName("dlgCombo")
    w.setFixedHeight(34)
    for opt in options:
        w.addItem(opt)
    if current and current in options:
        w.setCurrentText(current)
    return w


def _spin(value=None, min_val=0, max_val=9999):
    w = QSpinBox()
    w.setObjectName("dlgSpin")
    w.setFixedHeight(34)
    w.setRange(min_val, max_val)
    if value is not None:
        try:
            w.setValue(int(value))
        except (TypeError, ValueError):
            pass
    return w


# ─── Server Dialog ────────────────────────────────────────────────────────────

class ServerDialog(QDialog):
    """Add or Edit a server/storage device."""

    def __init__(self, server_data=None, parent=None):
        super().__init__(parent)
        self._data = server_data or {}
        is_edit = bool(server_data)
        self.setWindowTitle("Sunucu Düzenle" if is_edit else "Yeni Sunucu Ekle")
        self.setMinimumWidth(560)
        self.setMaximumHeight(700)
        self._init_ui()
        self.setObjectName("atlasDialog")

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setObjectName("dlgHeader")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 16, 20, 16)
        title_lbl = QLabel(self.windowTitle())
        title_lbl.setObjectName("dlgTitle")
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        root.addWidget(hdr)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("dlgScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("dlgBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 20, 24, 20)
        body_lay.setSpacing(6)

        d = self._data

        # ── Basic Info ──────────────────────────────────────────────────
        body_lay.addWidget(_section_title("TEMEL BİLGİLER"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_alias = _line("Sunucu 1", d.get('alias', ''))
        self.f_name = _line("10.10.1.249", d.get('name', ''))
        self.f_ip = _line("10.10.1.249:8006", d.get('ip_address', ''))
        self.f_type = _combo(['Server', 'Storage'], d.get('type', 'Server'))

        body_lay.addWidget(_FormField("Ad / Takma Ad", self.f_alias))
        body_lay.addWidget(_FormField("Base IP", self.f_name))
        body_lay.addWidget(_FormField("Erişim IP:Port", self.f_ip))
        body_lay.addWidget(_FormField("Tür", self.f_type))

        body_lay.addSpacing(12)

        # ── Credentials ─────────────────────────────────────────────────
        body_lay.addWidget(_section_title("ERİŞİM BİLGİLERİ"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_user = _line("root", d.get('username', ''))
        self.f_pass = _line("", d.get('password', ''))
        self.f_pass.setEchoMode(QLineEdit.Password)

        body_lay.addWidget(_FormField("Kullanıcı Adı", self.f_user))
        body_lay.addWidget(_FormField("Şifre", self.f_pass))

        body_lay.addSpacing(12)

        # ── Physical Resources ──────────────────────────────────────────
        body_lay.addWidget(_section_title("FİZİKSEL KAYNAKLAR"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_hostname = _line("ostim", d.get('hostname', ''))
        self.f_cpu_model = _line("Intel Xeon Silver 4210", d.get('cpu_model', ''))
        self.f_cpu_sockets = _spin(d.get('cpu_sockets'), 0, 64)
        self.f_cpu_threads = _spin(d.get('cpu_threads'), 0, 1024)
        self.f_total_ram = _line("125.54 GiB", d.get('total_ram', ''))
        self.f_sys_disk = _line("93.99 GiB", d.get('system_disk', ''))
        self.f_swap = _line("8.00 GiB", d.get('swap', ''))
        self.f_kernel = _line("Linux 6.8.4-2-pve", d.get('kernel', ''))
        self.f_pve = _line("8.2.2/...", d.get('pve_version', ''))
        self.f_boot = _combo(['', 'EFI', 'Legacy BIOS'], d.get('boot_mode', ''))
        self.f_pools = _line("local, local-lvm, TNAS01", d.get('storage_pools', ''))

        body_lay.addWidget(_FormField("Hostname", self.f_hostname))
        body_lay.addWidget(_FormField("CPU Modeli", self.f_cpu_model))
        body_lay.addWidget(_FormField("CPU Soket", self.f_cpu_sockets))
        body_lay.addWidget(_FormField("CPU Thread", self.f_cpu_threads))
        body_lay.addWidget(_FormField("Toplam RAM", self.f_total_ram))
        body_lay.addWidget(_FormField("Sistem Diski", self.f_sys_disk))
        body_lay.addWidget(_FormField("Swap", self.f_swap))
        body_lay.addWidget(_FormField("Kernel", self.f_kernel))
        body_lay.addWidget(_FormField("PVE Sürümü", self.f_pve))
        body_lay.addWidget(_FormField("Boot Mode", self.f_boot))
        body_lay.addWidget(_FormField("Depolama Havuzları", self.f_pools))

        body_lay.addSpacing(12)

        # ── Notes ───────────────────────────────────────────────────────
        body_lay.addWidget(_section_title("NOTLAR"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_notes = _text("", d.get('notes', ''))
        body_lay.addWidget(self.f_notes)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer buttons
        btn_frame = QFrame()
        btn_frame.setObjectName("dlgFooter")
        btn_lay = QHBoxLayout(btn_frame)
        btn_lay.setContentsMargins(20, 12, 20, 12)
        btn_lay.setSpacing(10)
        btn_lay.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setObjectName("dlgCancelBtn")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("dlgSaveBtn")
        save_btn.setFixedHeight(36)
        save_btn.setFixedWidth(120)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)

        btn_lay.addWidget(cancel_btn)
        btn_lay.addWidget(save_btn)
        root.addWidget(btn_frame)

    def _save(self):
        name = self.f_name.text().strip()
        alias = self.f_alias.text().strip()
        if not name:
            QMessageBox.warning(self, "Hata", "Base IP alanı zorunludur.")
            return
        if not alias:
            QMessageBox.warning(self, "Hata", "Ad / Takma Ad alanı zorunludur.")
            return

        boot_val = self.f_boot.currentText() or None

        self.result_data = {
            'name': name,
            'alias': alias,
            'ip_address': self.f_ip.text().strip() or None,
            'username': self.f_user.text().strip() or None,
            'password': self.f_pass.text() or None,
            'type': self.f_type.currentText(),
            'notes': self.f_notes.toPlainText().strip() or None,
            'hostname': self.f_hostname.text().strip() or None,
            'cpu_model': self.f_cpu_model.text().strip() or None,
            'cpu_sockets': self.f_cpu_sockets.value() or None,
            'cpu_threads': self.f_cpu_threads.value() or None,
            'total_ram': self.f_total_ram.text().strip() or None,
            'system_disk': self.f_sys_disk.text().strip() or None,
            'swap': self.f_swap.text().strip() or None,
            'kernel': self.f_kernel.text().strip() or None,
            'pve_version': self.f_pve.text().strip() or None,
            'boot_mode': boot_val,
            'storage_pools': self.f_pools.text().strip() or None,
        }
        self.accept()


# ─── VM Dialog ────────────────────────────────────────────────────────────────

class VMDialog(QDialog):
    """Add or Edit a virtual machine."""

    def __init__(self, servers, vm_data=None, preselect_server_id=None, parent=None):
        super().__init__(parent)
        self._servers = servers  # list of server dicts
        self._data = vm_data or {}
        is_edit = bool(vm_data)
        self.setWindowTitle("VM Düzenle" if is_edit else "Yeni VM Ekle")
        self.setMinimumWidth(540)
        self.setMaximumHeight(680)
        self._preselect = preselect_server_id
        self._init_ui()
        self.setObjectName("atlasDialog")

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setObjectName("dlgHeader")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 16, 20, 16)
        title_lbl = QLabel(self.windowTitle())
        title_lbl.setObjectName("dlgTitle")
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("dlgScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("dlgBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 20, 24, 20)
        body_lay.setSpacing(6)

        d = self._data

        # ── Server Selection ────────────────────────────────────────────
        body_lay.addWidget(_section_title("SUNUCU"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        server_names = [f"{s.get('alias','')} ({s.get('name','')})" for s in self._servers
                        if s.get('type') == 'Server']
        server_ids = [s['id'] for s in self._servers if s.get('type') == 'Server']
        self._server_ids = server_ids

        self.f_server = _combo(server_names)
        current_srv_id = d.get('server_id') or self._preselect
        if current_srv_id and current_srv_id in server_ids:
            self.f_server.setCurrentIndex(server_ids.index(current_srv_id))

        body_lay.addWidget(_FormField("Sunucu", self.f_server))
        body_lay.addSpacing(12)

        # ── VM Info ─────────────────────────────────────────────────────
        body_lay.addWidget(_section_title("VM BİLGİLERİ"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_vmid = _spin(d.get('vm_id', 0), 0, 99999)
        self.f_name = _line("web-server", d.get('name', ''))
        self.f_status = _combo(['running', 'stopped', ''], d.get('status', ''))
        self.f_ip = _line("10.10.1.x", d.get('ip_address', ''))

        body_lay.addWidget(_FormField("VM ID", self.f_vmid))
        body_lay.addWidget(_FormField("VM Adı", self.f_name))
        body_lay.addWidget(_FormField("Durum", self.f_status))
        body_lay.addWidget(_FormField("IP Adresi", self.f_ip))
        body_lay.addSpacing(12)

        # ── Resources ───────────────────────────────────────────────────
        body_lay.addWidget(_section_title("KAYNAKLAR"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_ram = _spin(d.get('ram_gb'), 0, 4096)
        self.f_ram.setSuffix(" GiB")
        self.f_cores = _spin(d.get('cores'), 0, 512)
        self.f_disk = _line("100G local-lvm", d.get('disk_info', ''))
        self.f_nic = _line("virtio, vmbr0", d.get('nic_info', ''))
        self.f_bios = _combo(['', 'SeaBIOS', 'OVMF (UEFI)'], d.get('bios_type', ''))
        self.f_machine = _line("i440fx", d.get('machine_type', ''))

        body_lay.addWidget(_FormField("RAM", self.f_ram))
        body_lay.addWidget(_FormField("vCPU / Core", self.f_cores))
        body_lay.addWidget(_FormField("Disk", self.f_disk))
        body_lay.addWidget(_FormField("NIC / MAC", self.f_nic))
        body_lay.addWidget(_FormField("BIOS", self.f_bios))
        body_lay.addWidget(_FormField("Makine Tipi", self.f_machine))
        body_lay.addSpacing(12)

        # ── Credentials ─────────────────────────────────────────────────
        body_lay.addWidget(_section_title("ERİŞİM BİLGİLERİ"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_user = _line("root", d.get('username', ''))
        self.f_pass = _line("", d.get('password', ''))
        self.f_pass.setEchoMode(QLineEdit.Password)

        body_lay.addWidget(_FormField("Kullanıcı Adı", self.f_user))
        body_lay.addWidget(_FormField("Şifre", self.f_pass))
        body_lay.addSpacing(12)

        # ── Notes ───────────────────────────────────────────────────────
        body_lay.addWidget(_section_title("NOTLAR"))
        body_lay.addWidget(_separator())
        body_lay.addSpacing(4)

        self.f_notes = _text("", d.get('notes', ''))
        body_lay.addWidget(self.f_notes)

        body_lay.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer
        btn_frame = QFrame()
        btn_frame.setObjectName("dlgFooter")
        btn_lay = QHBoxLayout(btn_frame)
        btn_lay.setContentsMargins(20, 12, 20, 12)
        btn_lay.setSpacing(10)
        btn_lay.addStretch()

        cancel_btn = QPushButton("İptal")
        cancel_btn.setObjectName("dlgCancelBtn")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(100)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Kaydet")
        save_btn.setObjectName("dlgSaveBtn")
        save_btn.setFixedHeight(36)
        save_btn.setFixedWidth(120)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save)

        btn_lay.addWidget(cancel_btn)
        btn_lay.addWidget(save_btn)
        root.addWidget(btn_frame)

    def _save(self):
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Hata", "VM Adı zorunludur.")
            return

        idx = self.f_server.currentIndex()
        server_id = self._server_ids[idx] if idx >= 0 and idx < len(self._server_ids) else None

        bios_val = self.f_bios.currentText() or None
        status_val = self.f_status.currentText() or None

        self.result_data = {
            'server_id': server_id,
            'vm_id': self.f_vmid.value(),
            'name': name,
            'ip_address': self.f_ip.text().strip() or None,
            'username': self.f_user.text().strip() or None,
            'password': self.f_pass.text() or None,
            'ram_gb': self.f_ram.value() or None,
            'cores': self.f_cores.value() or None,
            'disk_info': self.f_disk.text().strip() or None,
            'notes': self.f_notes.toPlainText().strip() or None,
            'status': status_val,
            'nic_info': self.f_nic.text().strip() or None,
            'bios_type': bios_val,
            'machine_type': self.f_machine.text().strip() or None,
        }
        self.accept()


# ─── About Dialog ─────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ATLAS Hakkında")
        self.setFixedSize(400, 380)
        self.setObjectName("atlasDialog")
        self._init_ui()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 36, 36, 28)
        lay.setSpacing(0)

        logo = QLabel("ATLAS")
        logo.setObjectName("aboutLogo")
        logo.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Sunucu Envanter Sistemi")
        tagline.setObjectName("aboutTagline")
        tagline.setAlignment(Qt.AlignCenter)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("dlgSeparator")

        lay.addWidget(logo)
        lay.addSpacing(6)
        lay.addWidget(tagline)
        lay.addSpacing(20)
        lay.addWidget(sep)
        lay.addSpacing(20)

        def info_row(label, value, value_obj=None):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 4, 0, 4)
            lbl = QLabel(label)
            lbl.setObjectName("aboutFieldLabel")
            lbl.setFixedWidth(110)
            val = QLabel(value)
            val.setObjectName(value_obj or "aboutFieldValue")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            rl.addWidget(lbl)
            rl.addWidget(val, 1)
            return row

        lay.addWidget(info_row("Versiyon", "1.1.0"))
        lay.addWidget(info_row("Geliştirici", "Ahmet Erol Bayrak", "aboutDevValue"))
        lay.addWidget(info_row("Kuruluş", "OSTIM Teknik Üniversitesi"))
        lay.addWidget(info_row("Veritabanı", "SQLite 3"))
        lay.addWidget(info_row("Arayüz", "PySide6 (Qt6)"))
        lay.addWidget(info_row("Platform", "Python 3"))

        lay.addSpacing(20)

        desc = QLabel(
            "ATLAS, ağ altyapısındaki Proxmox sunucularını,\n"
            "depolama birimlerini ve sanal makineleri merkezi\n"
            "olarak yönetmek için geliştirilmiş bir envanter\n"
            "yönetim sistemidir."
        )
        desc.setObjectName("aboutDesc")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()

        close_btn = QPushButton("Kapat")
        close_btn.setObjectName("dlgSaveBtn")
        close_btn.setFixedHeight(36)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)
