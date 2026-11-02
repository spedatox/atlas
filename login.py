from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QPainter, QColor, QLinearGradient


class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ATLAS — Giriş")
        self.setFixedSize(420, 610)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._init_ui()
        QShortcut(QKeySequence("Return"), self).activated.connect(self._try_login)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.reject)

    # ── Dragging ──────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── UI ────────────────────────────────────────────────────────────────────
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("loginCard")
        root.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(44, 44, 44, 36)
        lay.setSpacing(0)

        # ── Brand ──────────────────────────────────────────────────────
        logo = QLabel("ATLAS")
        logo.setObjectName("loginLogo")
        logo.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Sunucu Envanter Sistemi")
        tagline.setObjectName("loginTagline")
        tagline.setAlignment(Qt.AlignCenter)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("loginDivider")

        lay.addWidget(logo)
        lay.addSpacing(4)
        lay.addWidget(tagline)
        lay.addSpacing(28)
        lay.addWidget(divider)
        lay.addSpacing(28)

        # ── Subtitle ───────────────────────────────────────────────────
        subtitle = QLabel("Sisteme Giriş")
        subtitle.setObjectName("loginSubtitle")
        lay.addWidget(subtitle)
        lay.addSpacing(20)

        # ── Username ───────────────────────────────────────────────────
        user_lbl = QLabel("Kullanıcı Adı")
        user_lbl.setObjectName("loginFieldLabel")
        lay.addWidget(user_lbl)
        lay.addSpacing(6)

        self.username_input = QLineEdit()
        self.username_input.setObjectName("loginInput")
        self.username_input.setPlaceholderText("admin")
        self.username_input.setText("admin")
        self.username_input.setFixedHeight(42)
        lay.addWidget(self.username_input)
        lay.addSpacing(16)

        # ── Password ───────────────────────────────────────────────────
        pw_lbl = QLabel("Şifre")
        pw_lbl.setObjectName("loginFieldLabel")
        lay.addWidget(pw_lbl)
        lay.addSpacing(6)

        pw_row = QHBoxLayout()
        pw_row.setSpacing(0)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("loginInput")
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedHeight(42)
        pw_row.addWidget(self.password_input)
        lay.addLayout(pw_row)
        lay.addSpacing(10)

        # ── Error label ────────────────────────────────────────────────
        self.error_lbl = QLabel("")
        self.error_lbl.setObjectName("loginError")
        self.error_lbl.setAlignment(Qt.AlignCenter)
        self.error_lbl.setWordWrap(True)
        self.error_lbl.setFixedHeight(44)
        lay.addWidget(self.error_lbl)
        lay.addSpacing(16)

        # ── Login button ───────────────────────────────────────────────
        self.login_btn = QPushButton("Giriş Yap")
        self.login_btn.setObjectName("loginBtn")
        self.login_btn.setFixedHeight(46)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.clicked.connect(self._try_login)
        lay.addWidget(self.login_btn)

        source_btn = QPushButton('Veri Kaynağı / Uzak Sunucu')
        source_btn.setObjectName('toggleBtn')
        source_btn.clicked.connect(self._open_backend)
        lay.addSpacing(10)
        lay.addWidget(source_btn)

        lay.addStretch()

        # ── Footer ─────────────────────────────────────────────────────
        footer_sep = QFrame()
        footer_sep.setFrameShape(QFrame.HLine)
        footer_sep.setObjectName("loginDivider")
        lay.addWidget(footer_sep)
        lay.addSpacing(14)

        footer = QLabel("Geliştirici: <b>Ahmet Erol Bayrak</b>  ·  OSTIM Teknik Üniversitesi")
        footer.setObjectName("loginFooter")
        footer.setAlignment(Qt.AlignCenter)
        lay.addWidget(footer)

        # ── Close button ───────────────────────────────────────────────
        close_btn = QPushButton("✕")
        close_btn.setObjectName("loginCloseBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setParent(card)
        close_btn.move(420 - 28 - 12, 12)
        close_btn.clicked.connect(self.reject)

    # ── Auth ──────────────────────────────────────────────────────────────────
    def _open_backend(self):
        from storage_dialogs import BackendDialog
        from PySide6.QtWidgets import QMessageBox
        try:
            BackendDialog(self).exec()
        except Exception as exc:
            QMessageBox.critical(self, 'Veri Kaynağı Hatası', str(exc))

    def _try_login(self):
        if not self.login_btn.isEnabled():
            return
        from backends import db_manager
        from tasks import run_task
        username = self.username_input.text().strip()
        password = self.password_input.text()

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Kontrol ediliyor...")

        def checked(authenticated):
            if authenticated:
                self.accept()
            else:
                self.error_lbl.setText("Hatalı kullanıcı adı veya şifre")
                self.password_input.clear()
                self.password_input.setFocus()
                # Shake animation
                orig = self.x()
                for i, dx in enumerate([8, -8, 6, -6, 4, -4, 0]):
                    QTimer.singleShot(i * 40, lambda x=orig + dx: self.move(x, self.y()))
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Giriş Yap")

        def failed(message):
            self.error_lbl.setText(message)
            self.login_btn.setEnabled(True)
            self.login_btn.setText('Giriş Yap')

        run_task(self, 'Giriş kontrol ediliyor...',
                 lambda: db_manager.authenticate(username, password), checked, failed)
