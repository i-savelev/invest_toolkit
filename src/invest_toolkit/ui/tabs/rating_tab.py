from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class RatingTab(QWidget):
    """Заглушка вкладки 'Рейтинг'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("⭐ Рейтинг\n\nЗдесь будет таблица инвестиционных рейтингов")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: gray;")
        layout.addWidget(label)