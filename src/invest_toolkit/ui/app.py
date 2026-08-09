import sys
import logging
from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from .main_window import MainWindow


def run():
    """Точка входа GUI-приложения."""
    # Настраиваем корневой логгер до создания QApplication
    logging.getLogger("log").setLevel(logging.DEBUG)

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_teal.xml")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())