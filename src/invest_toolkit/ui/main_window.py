from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget
from PyQt6.QtCore import Qt

from .tabs.portfolio_tab import PortfolioTab
from .tabs.analysis_tab import AnalysisTab
from .tabs.rating_tab import RatingTab
from .tabs.parsing_tab import ParsingTab
from .log_panel import LogPanel


class MainWindow(QMainWindow):
    WINDOW_TITLE = "Invest Toolkit"
    MIN_WIDTH = 1000
    MIN_HEIGHT = 700

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._center_window()

        # Вкладки
        self.tabs = QTabWidget()

        self.portfolio_tab = PortfolioTab()
        self.analysis_tab = AnalysisTab()
        self.rating_tab = RatingTab()
        self.parsing_tab = ParsingTab()
        self.log_panel = LogPanel()

        # Основные вкладки
        self.tabs.addTab(self.portfolio_tab, "📊 Портфель")
        self.tabs.addTab(self.analysis_tab, "📈 Анализ")
        self.tabs.addTab(self.rating_tab, "⭐ Рейтинг")
        self.tabs.addTab(self.parsing_tab, "🔄 Парсинг")

        # --- Визуальный разделитель ---
        spacer = QWidget()
        spacer_idx = self.tabs.addTab(spacer, "      ")
        self.tabs.setTabEnabled(spacer_idx, False)
        self.tabs.tabBar().setTabTextColor(spacer_idx, Qt.GlobalColor.transparent)
        # --- Конец разделителя ---

        # Лог — последняя вкладка, визуально отделена
        self.tabs.addTab(self.log_panel, "📋  Лог")

        self.setCentralWidget(self.tabs)

        # Передаём ссылку на лог-панель в портфельную вкладку
        self.portfolio_tab.set_log_panel(self.log_panel)

    def _center_window(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.MIN_WIDTH) // 2 + geo.x()
            y = (geo.height() - self.MIN_HEIGHT) // 2 + geo.y()
            self.move(x, y)