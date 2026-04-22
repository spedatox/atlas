import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ATLAS")
    app.setOrganizationName("OSTIM")
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.qss")
    try:
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Stil dosyası yüklenemedi: {e}")

    from login import LoginWindow
    login = LoginWindow()
    login.move(
        app.primaryScreen().geometry().center().x() - login.width() // 2,
        app.primaryScreen().geometry().center().y() - login.height() // 2,
    )

    if login.exec():
        from ui_main import MainWindow
        window = MainWindow()
        window.resize(1340, 820)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
