from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class ParsingTab(QWidget):
    """Заглушка вкладки 'Парсинг'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("🔄 Парсинг\n\nЗдесь будет управление загрузкой данных SmartLab")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: gray;")
        layout.addWidget(label)