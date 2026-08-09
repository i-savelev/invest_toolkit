from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class AnalysisTab(QWidget):
    """Заглушка вкладки 'Анализ'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("📈 Анализ\n\nЗдесь будут графики финансовых показателей")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; color: gray;")
        layout.addWidget(label)