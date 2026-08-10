import sys
import logging
from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet

from .main_window import MainWindow
from .cache import setup_moex_cache


def run():
    """Точка входа GUI-приложения."""
    logging.getLogger("log").setLevel(logging.DEBUG)

    # Активируем кэш MOEX до создания любых воркеров
    setup_moex_cache()

    app = QApplication(sys.argv)
    apply_stylesheet(app, theme="dark_teal.xml")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())