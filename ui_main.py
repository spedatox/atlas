from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QLabel,
    QFrame, QScrollArea, QPushButton, QApplication,
    QStyledItemDelegate, QSplitter, QSizePolicy,
    QStyle, QStatusBar, QAbstractItemView, QMessageBox,
    QMenuBar, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import (QPainter, QFont, QColor, QFontMetrics,
                            QPen, QShortcut, QKeySequence, QAction)
from backends import db_manager
from tasks import run_task


# ── Custom Tree Delegate ───────────────────────────────────────────────────────

class InventoryDelegate(QStyledItemDelegate):

    STATUS_COLORS = {
        'running': QColor("#9ece6a"),
        'stopped': QColor("#f7768e"),
    }

    def paint(self, painter, option, index):
        painter.save()
        data = index.data(Qt.UserRole)
        if not data:
            super().paint(painter, option, index)
            painter.restore()
            return

        rect = option.rect
        is_sel = bool(option.state & QStyle.State_Selected)
        is_hov = bool(option.state & QStyle.State_MouseOver)

        if is_sel:
            painter.fillRect(rect, QColor("#1e3a5f"))
        elif is_hov:
            painter.fillRect(rect, QColor("#262940"))
        else:
            painter.fillRect(rect, QColor("transparent"))

        node_type = data.get('node_type')
        if node_type == 'server':
            self._paint_server(painter, rect, data, is_sel)
        elif node_type == 'vm':
            self._paint_vm(painter, rect, data, is_sel)

        painter.restore()

    def _paint_server(self, p, rect, data, is_sel):
        server = data['data']
        srv_type = server.get('type', 'Server')
        accent = QColor("#7aa2f7") if srv_type == 'Server' else QColor("#e0af68")

        p.fillRect(QRect(rect.x(), rect.y() + 6, 3, rect.height() - 12), accent)

        x = rect.x() + 14

        f1 = QFont("Consolas", 11, QFont.Bold)
        p.setFont(f1)
        p.setPen(QColor("#ffffff") if is_sel else QColor("#c0caf5"))
        p.drawText(QRect(x, rect.y() + 5, rect.width() - x - 60, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, server.get('name', ''))

        f2 = QFont("Segoe UI", 9)
        p.setFont(f2)
        p.setPen(QColor("#7081b0") if not is_sel else QColor("#8990b8"))
        vms = data.get('vms', [])
        vm_count = len(vms)

        alias = server.get('alias', '')
        total_ram = server.get('total_ram', '')
        sub = f"{alias}"
        if total_ram:
            sub += f"  ·  {total_ram}"

        p.drawText(QRect(x, rect.y() + 28, rect.width() - x - 60, 16),
                   Qt.AlignLeft | Qt.AlignVCenter, sub)

        badge_txt = str(vm_count) if vm_count > 0 else ""
        if badge_txt:
            bf = QFont("Segoe UI", 8, QFont.Bold)
            p.setFont(bf)
            fm = QFontMetrics(bf)
            bw = fm.horizontalAdvance(badge_txt) + 14
            br = QRect(rect.right() - bw - 8, rect.y() + rect.height() // 2 - 10, bw, 20)
            p.setBrush(accent)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(br, 10, 10)
            p.setPen(QColor("#1a1b26"))
            p.drawText(br, Qt.AlignCenter, badge_txt)

    def _paint_vm(self, p, rect, data, is_sel):
        vm = data['data']
        x = rect.x() + 6

        # Status dot
        status = (vm.get('status') or '').lower()
        dot_color = self.STATUS_COLORS.get(status)
        if dot_color:
            p.setBrush(dot_color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(x, rect.y() + rect.height() // 2 - 4, 8, 8)
            x += 14
        else:
            x += 4

        # VMID badge
        vid = str(vm.get('vm_id', '?'))
        id_font = QFont("Consolas", 9)
        p.setFont(id_font)
        fm = QFontMetrics(id_font)
        bw = max(fm.horizontalAdvance(vid) + 12, 42)
        br = QRect(x, rect.y() + rect.height() // 2 - 9, bw, 18)
        p.setBrush(QColor("#252840"))
        p.setPen(QPen(QColor("#3d4470"), 1))
        p.drawRoundedRect(br, 3, 3)
        p.setPen(QColor("#7aa2f7") if not is_sel else QColor("#c0caf5"))
        p.drawText(br, Qt.AlignCenter, vid)

        # VM name
        x += bw + 8
        nf = QFont("Segoe UI", 10)
        p.setFont(nf)
        p.setPen(QColor("#a9b1d6") if not is_sel else QColor("#ffffff"))
        p.drawText(QRect(x, rect.y(), rect.width() - x - 8, rect.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, vm.get('name', ''))

    def sizeHint(self, option, index):
        data = index.data(Qt.UserRole)
        if data and data.get('node_type') == 'server':
            return QSize(200, 52)
        return QSize(200, 36)


# ── Utility Widgets ────────────────────────────────────────────────────────────

class CopyButton(QPushButton):
    def __init__(self, text_to_copy, label="Kopyala", parent=None):
        super().__init__(label, parent)
        self._text = text_to_copy or ''
        self._orig = label
        self.setObjectName("copyBtn")
        self.setFixedHeight(26)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._do_copy)

    def _do_copy(self):
        QApplication.clipboard().setText(self._text)
        self.setText("✓ Kopyalandı")
        self.setObjectName("copyBtnDone")
        self.style().polish(self)
        QTimer.singleShot(1800, self._reset)

    def _reset(self):
        self.setText(self._orig)
        self.setObjectName("copyBtn")
        self.style().polish(self)


class PasswordWidget(QWidget):
    def __init__(self, password, parent=None):
        super().__init__(parent)
        self._pw = password or ''
        self._visible = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._lbl = QLabel('●' * min(len(self._pw), 16))
        self._lbl.setObjectName("pwMasked")

        self._eye = QPushButton("Göster")
        self._eye.setObjectName("toggleBtn")
        self._eye.setFixedSize(62, 26)
        self._eye.setCursor(Qt.PointingHandCursor)
        self._eye.clicked.connect(self._toggle)

        self._copy = CopyButton(self._pw)
        self._copy.setFixedSize(82, 26)

        lay.addWidget(self._lbl, 1)
        lay.addWidget(self._eye)
        lay.addWidget(self._copy)

    def _toggle(self):
        self._visible = not self._visible
        if self._visible:
            self._lbl.setText(self._pw)
            self._lbl.setObjectName("pwVisible")
            self._eye.setText("Gizle")
        else:
            self._lbl.setText('●' * min(len(self._pw), 16))
            self._lbl.setObjectName("pwMasked")
            self._eye.setText("Göster")
        self._lbl.style().polish(self._lbl)


class FieldRow(QWidget):
    def __init__(self, label, value, copyable=False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 3, 0, 3)
        lay.setSpacing(8)

        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        lbl.setFixedWidth(130)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        val_text = str(value) if value is not None else "—"
        val = QLabel(val_text)
        val.setObjectName("fieldValue")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)

        lay.addWidget(lbl)
        lay.addWidget(val, 1)

        if copyable and value:
            btn = CopyButton(str(value))
            btn.setFixedSize(82, 26)
            lay.addWidget(btn)


class DetailSection(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("detailSection")
        main = QVBoxLayout(self)
        main.setContentsMargins(16, 12, 16, 14)
        main.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        main.addWidget(title_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("sectionSep")
        main.addWidget(sep)
        main.addSpacing(8)

        self._content = QVBoxLayout()
        self._content.setSpacing(2)
        main.addLayout(self._content)

    def add_field(self, label, value, copyable=False):
        self._content.addWidget(FieldRow(label, value, copyable))

    def add_password(self, label, password):
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 3, 0, 3)
        rl.setSpacing(8)

        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        lbl.setFixedWidth(130)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        pw = PasswordWidget(password)

        rl.addWidget(lbl)
        rl.addWidget(pw, 1)
        self._content.addWidget(row)

    def add_widget(self, w):
        self._content.addWidget(w)


# ── Main Window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATLAS — Sunucu Envanter Sistemi")
        self.inventory = []
        self._current_server = None
        self._current_vm = None
        self._current_parent = None
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        # ── Menu Bar ──────────────────────────────────────────────────────
        self._build_menu()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

        # ── Left Panel ────────────────────────────────────────────────────
        left = QFrame()
        left.setObjectName("leftPanel")
        left.setMinimumWidth(280)
        left.setMaximumWidth(420)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # Top bar with branding + add button
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        tbl = QHBoxLayout(top_bar)
        tbl.setContentsMargins(16, 14, 12, 12)
        tbl.setSpacing(8)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(2)

        atlas_lbl = QLabel("ATLAS")
        atlas_lbl.setObjectName("atlasLogo")
        sub_lbl = QLabel("Sunucu Envanter Sistemi")
        sub_lbl.setObjectName("atlasSub")

        brand_col.addWidget(atlas_lbl)
        brand_col.addWidget(sub_lbl)
        tbl.addLayout(brand_col, 1)

        add_srv_btn = QPushButton("+ Sunucu")
        add_srv_btn.setObjectName("addServerBtn")
        add_srv_btn.setFixedHeight(30)
        add_srv_btn.setCursor(Qt.PointingHandCursor)
        add_srv_btn.setToolTip("Yeni sunucu ekle")
        add_srv_btn.clicked.connect(self._add_server)
        tbl.addWidget(add_srv_btn)

        # Search bar
        search_wrap = QFrame()
        search_wrap.setObjectName("searchWrap")
        swl = QVBoxLayout(search_wrap)
        swl.setContentsMargins(12, 10, 12, 10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Sunucu veya VM ara...  (Ctrl+F)")
        self.search.setObjectName("searchBar")
        self.search.textChanged.connect(self._filter_tree)

        swl.addWidget(self.search)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("inventoryTree")
        self.tree.setItemDelegate(InventoryDelegate())
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(False)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setMouseTracking(True)
        self.tree.viewport().setMouseTracking(True)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)

        ll.addWidget(top_bar)
        ll.addWidget(search_wrap)
        ll.addWidget(self.tree, 1)

        # ── Right Panel ───────────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("rightPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setObjectName("detailScroll")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.detail_widget = QWidget()
        self.detail_widget.setObjectName("detailContent")
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(32, 28, 32, 28)
        self.detail_layout.setSpacing(12)
        self.detail_layout.setAlignment(Qt.AlignTop)

        self._show_placeholder()

        self.scroll.setWidget(self.detail_widget)
        rl.addWidget(self.scroll)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([310, 970])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Status bar
        sb = QStatusBar()
        sb.setObjectName("mainStatusBar")
        self.setStatusBar(sb)
        self._status = sb

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.search.setFocus)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._add_server)
        QShortcut(QKeySequence("F5"), self).activated.connect(self._load_data)

    def _build_menu(self):
        mb = self.menuBar()
        mb.setObjectName("mainMenuBar")

        # File menu
        file_menu = mb.addMenu("Dosya")
        file_menu.setObjectName("mainMenu")

        act_refresh = QAction("Yenile  (F5)", self)
        act_refresh.triggered.connect(self._load_data)
        file_menu.addAction(act_refresh)

        for text, slot in (('Bellek / Envanter Yedeği Al...', self._backup_inventory),
                           ('Envanter İçe Aktar...', self._import_inventory)):
            action = QAction(text, self)
            action.triggered.connect(slot)
            file_menu.addAction(action)

        file_menu.addSeparator()

        act_exit = QAction("Çıkış", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Inventory menu
        inv_menu = mb.addMenu("Envanter")
        inv_menu.setObjectName("mainMenu")

        act_add_srv = QAction("+ Yeni Sunucu  (Ctrl+N)", self)
        act_add_srv.triggered.connect(self._add_server)
        inv_menu.addAction(act_add_srv)

        act_add_vm = QAction("+ Yeni VM", self)
        act_add_vm.triggered.connect(lambda: self._add_vm())
        inv_menu.addAction(act_add_vm)

        # Help menu
        help_menu = mb.addMenu("Yardım")
        help_menu.setObjectName("mainMenu")

        act_about = QAction("ATLAS Hakkında", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_data(self):
        run_task(self, 'Envanter yükleniyor...', db_manager.get_inventory,
                 self._data_loaded, self._storage_error)

    def _storage_error(self, message):
        QMessageBox.critical(self, 'Veri İşlemi Başarısız', message)

    def _data_loaded(self, inventory):
        self.inventory = inventory
        self._populate_tree()
        self._filter_tree(self.search.text())
        if self._current_vm:
            selected = next(((vm, s) for s in inventory for vm in s['vms']
                             if vm['id'] == self._current_vm['id']), None)
            if selected:
                self._show_vm(*selected)
            else:
                self._current_vm = self._current_parent = None
                self._show_placeholder()
        elif self._current_server:
            selected = next((s for s in inventory if s['id'] == self._current_server['id']), None)
            if selected:
                self._show_server(selected)
            else:
                self._current_server = None
                self._show_placeholder()
        servers = sum(1 for s in self.inventory if s.get('type') == 'Server')
        storages = sum(1 for s in self.inventory if s.get('type') == 'Storage')
        vms = sum(len(s.get('vms', [])) for s in self.inventory)
        self._status.showMessage(
            f"  {servers} Proxmox Sunucu  ·  {storages} Depolama  ·  {vms} Sanal Makine"
            + ('  ·  Uzak sunucu' if db_manager.mode == 'remote' else '  ·  Yerel SQLite')
        )

    def _backup_inventory(self):
        from datetime import datetime
        filters = 'ATLAS JSON (*.json)'
        if db_manager.mode == 'local':
            filters += ';;Tam SQLite Yedeği (*.db)'
        path, selected = QFileDialog.getSaveFileName(
            self, 'Envanter Yedeği Al', f'atlas-backup-{datetime.now():%Y%m%d-%H%M%S}', filters)
        if not path:
            return
        sqlite_backup = '*.db' in selected
        extension = '.db' if sqlite_backup else '.json'
        if not path.lower().endswith(extension):
            path += extension
        operation = db_manager.create_backup if sqlite_backup else db_manager.export_backup
        run_task(self, 'Yedek hazırlanıyor...', lambda: operation(path),
                 lambda saved: QMessageBox.information(self, 'Yedek Kaydedildi',
                     f'Yedek: {saved}\n\nBu dosya erişim şifreleri içerir. Güvenli bir yerde saklayın.'),
                 self._storage_error)

    def _import_inventory(self):
        from inventory_io import read_document
        path, _ = QFileDialog.getOpenFileName(self, 'Envanter İçe Aktar', '',
                                               'ATLAS Yedeği (*.json *.db *.sqlite *.sqlite3);;Tüm Dosyalar (*)')
        if not path:
            return
        run_task(self, 'Yedek doğrulanıyor...', lambda: read_document(path),
                 self._preview_import, self._storage_error)

    def _preview_import(self, document):
        from storage_dialogs import ImportDialog
        dialog = ImportDialog(document, self)
        if not dialog.exec():
            return
        mode = dialog.mode.currentData()

        def imported(result):
            self._show_placeholder()
            self._current_server = self._current_vm = self._current_parent = None
            QMessageBox.information(self, 'İçe Aktarma Tamamlandı',
                f"Eklenen: {result['servers_added']} sunucu, {result['vms_added']} VM\n"
                f"Korunan: {result['servers_skipped']} sunucu, {result['vms_skipped']} VM\n\n"
                f"Kurtarma yedeği: {result['backup_path']}")
            self._load_data()

        # Import the already reviewed document, without reopening a potentially changed file.
        run_task(self, 'Envanter içe aktarılıyor...',
                 lambda: db_manager.import_document(document, mode), imported, self._storage_error)

    def _populate_tree(self):
        self.tree.clear()
        servers = [s for s in self.inventory if s.get('type') == 'Server']
        storages = [s for s in self.inventory if s.get('type') == 'Storage']

        def make_group(title):
            g = QTreeWidgetItem(self.tree)
            g.setText(0, title)
            g.setData(0, Qt.UserRole, None)
            g.setFlags(Qt.ItemIsEnabled)
            f = QFont("Segoe UI", 8)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
            f.setBold(True)
            g.setFont(0, f)
            g.setForeground(0, QColor("#565f89"))
            return g

        if servers:
            grp = make_group("PROXMOX SUNUCULAR")
            for s in servers:
                item = QTreeWidgetItem(grp)
                item.setData(0, Qt.UserRole, {
                    'node_type': 'server',
                    'data': s,
                    'vms': s['vms']
                })
                item.setSizeHint(0, QSize(200, 52))
                for vm in s['vms']:
                    vi = QTreeWidgetItem(item)
                    vi.setData(0, Qt.UserRole, {
                        'node_type': 'vm',
                        'data': vm,
                        'parent': s
                    })
                    vi.setSizeHint(0, QSize(200, 36))

        if storages:
            grp2 = make_group("DEPOLAMA")
            for s in storages:
                item = QTreeWidgetItem(grp2)
                item.setData(0, Qt.UserRole, {
                    'node_type': 'server',
                    'data': s,
                    'vms': []
                })
                item.setSizeHint(0, QSize(200, 52))

        self.tree.expandAll()

    def _filter_tree(self, text):
        q = text.lower().strip()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            grp = root.child(i)
            grp.setHidden(False)
            any_visible = False
            for j in range(grp.childCount()):
                srv_item = grp.child(j)
                d = srv_item.data(0, Qt.UserRole)
                srv = d['data'] if d else {}
                srv_match = not q or q in srv.get('name', '').lower() or q in srv.get('alias', '').lower()
                child_match = False
                for k in range(srv_item.childCount()):
                    vm_item = srv_item.child(k)
                    vd = vm_item.data(0, Qt.UserRole)
                    vm = vd['data'] if vd else {}
                    vm_match = (not q or q in vm.get('name', '').lower()
                                or q in str(vm.get('vm_id', '')))
                    vm_item.setHidden(not vm_match and not srv_match)
                    if vm_match:
                        child_match = True
                visible = srv_match or child_match
                srv_item.setHidden(not visible)
                if visible:
                    any_visible = True
                    if srv_match:
                        for k in range(srv_item.childCount()):
                            srv_item.child(k).setHidden(False)
            if not any_visible and q:
                grp.setHidden(True)

    # ── Tree Events ───────────────────────────────────────────────────────────

    def _on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if not data:
            item.setExpanded(not item.isExpanded())
            return
        if data['node_type'] == 'server':
            self._current_server = data['data']
            self._current_vm = None
            self._current_parent = None
            self._show_server(data['data'])
        elif data['node_type'] == 'vm':
            self._current_vm = data['data']
            self._current_parent = data.get('parent')
            self._current_server = None
            self._show_vm(data['data'], data.get('parent'))

    def _tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)
        menu.setObjectName("contextMenu")

        if data['node_type'] == 'server':
            edit_act = menu.addAction("Düzenle")
            add_vm_act = menu.addAction("VM Ekle")
            menu.addSeparator()
            del_act = menu.addAction("Sil")

            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action == edit_act:
                self._edit_server(data['data'])
            elif action == add_vm_act:
                self._add_vm(preselect_server_id=data['data'].get('id'))
            elif action == del_act:
                self._delete_server(data['data'])

        elif data['node_type'] == 'vm':
            edit_act = menu.addAction("Düzenle")
            menu.addSeparator()
            del_act = menu.addAction("Sil")

            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action == edit_act:
                self._edit_vm(data['data'])
            elif action == del_act:
                self._delete_vm(data['data'])

    # ── Detail Panel Helpers ──────────────────────────────────────────────────

    def _clear_detail(self):
        while self.detail_layout.count():
            child = self.detail_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _show_placeholder(self):
        self._clear_detail()
        ph = QLabel("← Bir sunucu veya VM seçin")
        ph.setObjectName("placeholder")
        ph.setAlignment(Qt.AlignCenter)
        self.detail_layout.addWidget(ph)
        self.detail_layout.addStretch()

    def _add_header(self, badge_text, badge_obj, title, subtitle=None, copy_val=None,
                    on_edit=None, on_delete=None, on_add_vm=None):
        hdr = QWidget()
        hdr.setObjectName("detailHeader")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(0, 0, 0, 8)
        hl.setSpacing(5)

        # Top row: badge + action buttons
        top_row = QHBoxLayout()
        badge = QLabel(badge_text)
        badge.setObjectName(badge_obj)
        badge.setFixedHeight(22)
        top_row.addWidget(badge)
        top_row.addStretch()

        if on_add_vm:
            add_vm_btn = QPushButton("+ VM Ekle")
            add_vm_btn.setObjectName("actionAddBtn")
            add_vm_btn.setFixedHeight(26)
            add_vm_btn.setCursor(Qt.PointingHandCursor)
            add_vm_btn.clicked.connect(on_add_vm)
            top_row.addWidget(add_vm_btn)

        if on_edit:
            edit_btn = QPushButton("Düzenle")
            edit_btn.setObjectName("actionEditBtn")
            edit_btn.setFixedHeight(26)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(on_edit)
            top_row.addWidget(edit_btn)

        if on_delete:
            del_btn = QPushButton("Sil")
            del_btn.setObjectName("actionDeleteBtn")
            del_btn.setFixedHeight(26)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(on_delete)
            top_row.addWidget(del_btn)

        hl.addLayout(top_row)

        title_row = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setObjectName("detailTitle")
        title_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_row.addWidget(title_lbl)

        if copy_val:
            cb = CopyButton(copy_val, "IP Kopyala")
            cb.setFixedSize(90, 28)
            title_row.addWidget(cb)
        title_row.addStretch()
        hl.addLayout(title_row)

        if subtitle:
            sl = QLabel(subtitle)
            sl.setObjectName("detailSubtitle")
            hl.addWidget(sl)

        self.detail_layout.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("headerSep")
        self.detail_layout.addWidget(sep)
        self.detail_layout.addSpacing(4)

    # ── Server Detail ─────────────────────────────────────────────────────────

    def _show_server(self, server):
        self._current_server = server
        self._current_vm = self._current_parent = None
        self._clear_detail()
        srv_type = server.get('type', 'Server')
        is_storage = srv_type == 'Storage'

        self._add_header(
            "DEPOLAMA" if is_storage else "PROXMOX SUNUCU",
            "badgeStorage" if is_storage else "badgeServer",
            server.get('name', ''),
            server.get('alias', ''),
            server.get('name', ''),
            on_edit=lambda: self._edit_server(server),
            on_delete=lambda: self._delete_server(server),
            on_add_vm=(lambda: self._add_vm(preselect_server_id=server.get('id'))) if not is_storage else None,
        )

        # Connection section
        conn = DetailSection("Bağlantı Bilgileri")
        ip_addr = server.get('ip_address', server.get('name', ''))

        if not is_storage:
            url = f"https://{ip_addr}"
            conn.add_field("Proxmox URL", url, copyable=True)
        else:
            conn.add_field("IP Adresi", ip_addr, copyable=True)

        uname = server.get('username')
        conn.add_field("Kullanıcı Adı", uname if uname else "—", copyable=bool(uname))

        if server.get('password'):
            conn.add_password("Şifre", server.get('password'))
        else:
            notes = server.get('notes') or 'Şifre bilgisi bulunamadı'
            conn.add_field("Şifre", notes)

        if server.get('notes') and server.get('password'):
            conn.add_field("Not", server.get('notes'))

        self.detail_layout.addWidget(conn)

        # Physical resources section (servers only)
        if not is_storage and any(server.get(k) for k in
                                   ('cpu_model', 'cpu_threads', 'total_ram', 'kernel')):
            res = DetailSection("Sistem Kaynakları")
            if server.get('hostname'):
                res.add_field("Hostname", server['hostname'])
            if server.get('cpu_model'):
                res.add_field("CPU Modeli", server['cpu_model'])

            cpu_line = []
            if server.get('cpu_sockets'):
                cpu_line.append(f"{server['cpu_sockets']} Soket")
            if server.get('cpu_threads'):
                cpu_line.append(f"{server['cpu_threads']} Thread")
            if cpu_line:
                res.add_field("CPU Yapısı", "  ·  ".join(cpu_line))

            if server.get('total_ram'):
                res.add_field("Toplam RAM", server['total_ram'])
            if server.get('system_disk'):
                res.add_field("Sistem Diski", server['system_disk'])
            if server.get('swap') and server['swap'] != 'N/A':
                res.add_field("Swap", server['swap'])
            if server.get('boot_mode'):
                res.add_field("Boot Mode", server['boot_mode'])
            if server.get('pve_version'):
                res.add_field("PVE Sürümü", server['pve_version'])
            if server.get('kernel'):
                res.add_field("Kernel", server['kernel'])
            if server.get('storage_pools'):
                res.add_field("Depolama Havuzları", server['storage_pools'])
            self.detail_layout.addWidget(res)

        # VMs section
        vms = server.get('vms', [])
        if vms:
            vm_sec = DetailSection(f"Sanal Makineler  ({len(vms)})")
            for vm in vms:
                vm_sec.add_widget(self._make_vm_row(vm, server))
            self.detail_layout.addWidget(vm_sec)

        self.detail_layout.addStretch()

    # ── VM Detail ─────────────────────────────────────────────────────────────

    def _show_vm(self, vm, parent_server):
        self._current_vm = vm
        self._current_parent = parent_server
        self._current_server = None
        self._clear_detail()

        pname = ''
        palias = ''
        if parent_server:
            pname = parent_server.get('name', '')
            palias = parent_server.get('alias', '')

        # Status badge
        status = (vm.get('status') or '').lower()
        status_display = "● Çalışıyor" if status == 'running' else ("○ Durduruldu" if status == 'stopped' else "")
        subtitle = f"Host: {pname}  ({palias})" if pname else None
        if status_display:
            subtitle = f"{status_display}   |   {subtitle}" if subtitle else status_display

        self._add_header(
            "SANAL MAKİNE",
            "badgeVM",
            vm.get('name', ''),
            subtitle,
            on_edit=lambda: self._edit_vm(vm),
            on_delete=lambda: self._delete_vm(vm),
        )

        # Resources
        info = DetailSection("Kaynak Bilgileri")
        info.add_field("VM ID", str(vm.get('vm_id', '?')))

        if vm.get('ip_address'):
            info.add_field("IP Adresi", vm['ip_address'], copyable=True)

        ram = vm.get('ram_gb')
        info.add_field("RAM", f"{int(ram)} GiB" if ram else "—")
        cores = vm.get('cores')
        info.add_field("vCPU", f"{cores} Çekirdek" if cores else "—")
        disk = vm.get('disk_info')
        info.add_field("Disk", disk if disk else "—")

        if vm.get('nic_info'):
            info.add_field("NIC / MAC", vm['nic_info'])
        if vm.get('bios_type'):
            info.add_field("BIOS", vm['bios_type'])
        if vm.get('machine_type'):
            info.add_field("Makine Tipi", vm['machine_type'])

        self.detail_layout.addWidget(info)

        # Credentials
        if vm.get('username') or vm.get('password'):
            cred = DetailSection("Erişim Bilgileri")
            if vm.get('username'):
                cred.add_field("Kullanıcı", vm.get('username'), copyable=True)
            if vm.get('password'):
                cred.add_password("Şifre", vm.get('password'))
            self.detail_layout.addWidget(cred)

        # Notes
        if vm.get('notes'):
            notes_sec = DetailSection("Notlar")
            nl = QLabel(vm.get('notes', ''))
            nl.setObjectName("noteLabel")
            nl.setWordWrap(True)
            notes_sec.add_widget(nl)
            self.detail_layout.addWidget(notes_sec)

        self.detail_layout.addStretch()

    def _make_vm_row(self, vm, parent_server):
        row = QFrame()
        row.setObjectName("vmRow")
        row.setCursor(Qt.PointingHandCursor)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)
        rl.setSpacing(8)

        # Status dot
        status = (vm.get('status') or '').lower()
        if status in ('running', 'stopped'):
            dot = QLabel("●")
            dot.setObjectName("vmStatusRunning" if status == 'running' else "vmStatusStopped")
            dot.setFixedWidth(12)
            rl.addWidget(dot)

        vid = QLabel(str(vm.get('vm_id', '?')))
        vid.setObjectName("vmIdBadge")
        vid.setFixedWidth(52)
        vid.setAlignment(Qt.AlignCenter)

        name = QLabel(vm.get('name', ''))
        name.setObjectName("vmName")

        rl.addWidget(vid)
        rl.addWidget(name, 1)

        # Resource pills
        if vm.get('ram_gb'):
            ram_lbl = QLabel(f"{int(vm['ram_gb'])}G")
            ram_lbl.setObjectName("vmResPill")
            rl.addWidget(ram_lbl)

        if vm.get('cores'):
            cpu_lbl = QLabel(f"{vm['cores']}c")
            cpu_lbl.setObjectName("vmResPill")
            rl.addWidget(cpu_lbl)

        if vm.get('notes'):
            note = QLabel(vm.get('notes', ''))
            note.setObjectName("vmNote")
            note.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rl.addWidget(note)

        # Click to show VM detail
        def _click(ev, v=vm, ps=parent_server):
            self._show_vm(v, ps)
        row.mousePressEvent = _click

        return row

    # ── CRUD: Server ──────────────────────────────────────────────────────────

    def _commit_change(self, operation):
        def changed():
            operation()
            return db_manager.get_inventory()
        run_task(self, 'Envanter kaydediliyor...', changed,
                 self._data_loaded, self._storage_error)

    def _add_server(self):
        from dialogs import ServerDialog
        dlg = ServerDialog(parent=self)
        if dlg.exec():
            self._commit_change(lambda: db_manager.add_server(dlg.result_data))

    def _edit_server(self, server):
        from dialogs import ServerDialog
        dlg = ServerDialog(server_data=server, parent=self)
        if dlg.exec():
            self._commit_change(lambda: db_manager.update_server(server['id'], dlg.result_data))

    def _delete_server(self, server):
        alias = server.get('alias', server.get('name', ''))
        vm_count = len(server.get('vms', []))
        msg = f"'{alias}' sunucusunu silmek istediğinize emin misiniz?"
        if vm_count:
            msg += f"\n\nBu işlem {vm_count} VM kaydını da silecektir!"
        reply = QMessageBox.question(self, "Sunucu Sil", msg,
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._commit_change(lambda: db_manager.delete_server(server['id']))

    # ── CRUD: VM ──────────────────────────────────────────────────────────────

    def _add_vm(self, preselect_server_id=None):
        from dialogs import VMDialog
        servers = [s for s in self.inventory if s.get('type') == 'Server']
        dlg = VMDialog(servers, preselect_server_id=preselect_server_id, parent=self)
        if dlg.exec():
            self._commit_change(lambda: db_manager.add_vm(dlg.result_data))

    def _edit_vm(self, vm):
        from dialogs import VMDialog
        servers = [s for s in self.inventory if s.get('type') == 'Server']
        dlg = VMDialog(servers, vm_data=vm, parent=self)
        if dlg.exec():
            self._commit_change(lambda: db_manager.update_vm(vm['id'], dlg.result_data))

    def _delete_vm(self, vm):
        name = vm.get('name', f"VM {vm.get('vm_id','?')}")
        reply = QMessageBox.question(self, "VM Sil",
                                     f"'{name}' VM'ini silmek istediğinize emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._commit_change(lambda: db_manager.delete_vm(vm['id']))

    # ── About ─────────────────────────────────────────────────────────────────

    def _show_about(self):
        from dialogs import AboutDialog
        AboutDialog(parent=self).exec()
