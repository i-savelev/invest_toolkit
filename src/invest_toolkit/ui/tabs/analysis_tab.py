import json
import math
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QMessageBox, QTableWidget, QTableWidgetItem,
    QScrollArea, QCheckBox, QSpinBox, QSplitter, QHeaderView,
    QAbstractItemView, QLineEdit, QInputDialog, QListWidget, QFrame,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from invest_toolkit.ui.widgets import FileSelector
from invest_toolkit.ui.workers.analysis_worker import AnalysisDataWorker
from invest_toolkit.viz.plots import plot_one_chart

try:
    from platformdirs import user_cache_dir
    CACHE_DIR = Path(user_cache_dir("InvestToolkit"))
except ImportError:
    import tempfile
    CACHE_DIR = Path(tempfile.gettempdir()) / "InvestToolkit"

CACHE_FILE = CACHE_DIR / "all_stock_info.csv"
PRESETS_FILE = CACHE_DIR / "analysis_presets.json"

NON_CHART_INDICATORS = {'url', 'name', 'isin', 'lot_size', 'price', 'cap',
                        'currency', 'coupon', 'type', 'free_float', 'ir',
                        'rating', 'rating_string'}

LEFT_COL_WIDTH = 240
REDRAW_DEBOUNCE_MS = 300


class AnalysisTab(QWidget):
    """Вкладка анализа компаний: графики финансовых показателей."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame | None = None
        self._worker = None
        self._metric_checkboxes: dict[str, QCheckBox] = {}

        self._build_ui()
        self._connect_signals()
        self._populate_presets_list()
        self._try_load_cache()
        self._alloc_tickers: set[str] = set()
    # ───────────────────────────────────────────────────────────── UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(6, 6, 6, 6)

        # === Компактный блок исходных данных ===
        files_layout = QGridLayout()
        files_layout.setContentsMargins(4, 4, 4, 4)
        files_layout.setHorizontalSpacing(6)
        files_layout.setVerticalSpacing(2)

        self._ff_selector = FileSelector(
            caption="Выберите файл free-float",
            file_filter="Excel файлы (*.xlsx *.xls);;Все файлы (*)",
        )
        self._ir_selector = FileSelector(
            caption="Выберите файл IR рейтинга",
            file_filter="Excel файлы (*.xlsx *.xls);;Все файлы (*)",
        )
        self._sl_selector = FileSelector(
            caption="Выберите папку с CSV SmartLab",
            directory=True,
        )

        files_layout.addWidget(QLabel("Free-float:"), 0, 0)
        files_layout.addWidget(self._ff_selector, 0, 1)
        files_layout.addWidget(QLabel("IR рейтинг:"), 0, 2)
        files_layout.addWidget(self._ir_selector, 0, 3)
        files_layout.addWidget(QLabel("SmartLab:"), 0, 4)
        files_layout.addWidget(self._sl_selector, 0, 5)

        self._generate_btn = QPushButton("🔄 Сформировать / Обновить")
        files_layout.addWidget(self._generate_btn, 0, 6)

        for col in (1, 3, 5):
            files_layout.setColumnStretch(col, 1)

        root.addLayout(files_layout)

        # === Основная область ===
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Левая колонка: компании --
        companies_widget = QWidget()
        companies_layout = QVBoxLayout(companies_widget)
        companies_layout.setContentsMargins(0, 0, 0, 0)
        companies_layout.setSpacing(4)

        # Селектор таблицы распределения (index_fund.xlsx)
        self._alloc_selector = FileSelector(
            caption="Выберите таблицу распределения",
            file_filter="Excel файлы (*.xlsx *.xls);;Все файлы (*)",
        )
        companies_layout.addWidget(self._alloc_selector)

        # Переключатель фильтра
        self._alloc_only_checkbox = QCheckBox("Только из распределения")
        companies_layout.addWidget(self._alloc_only_checkbox)
        self._company_search = QLineEdit()
        self._company_search.setPlaceholderText("🔍 Поиск по тикеру или названию...")
        self._company_search.setClearButtonEnabled(True)
        companies_layout.addWidget(self._company_search)

        self._company_table = QTableWidget()
        self._company_table.setColumnCount(2)
        self._company_table.setHorizontalHeaderLabels(["Тикер", "Название"])
        self._company_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._company_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._company_table.verticalHeader().setVisible(False)
        self._company_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._company_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._company_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        companies_layout.addWidget(self._company_table, 1)

        # --- Средняя колонка: показатели + пресеты ---
        metrics_widget = QWidget()
        metrics_layout = QVBoxLayout(metrics_widget)
        metrics_layout.setContentsMargins(4, 0, 0, 0)
        metrics_layout.setSpacing(4)

        self._metric_search = QLineEdit()
        self._metric_search.setPlaceholderText("🔍 Поиск показателя...")
        self._metric_search.setClearButtonEnabled(True)
        metrics_layout.addWidget(self._metric_search)

        # Чекбоксы показателей
        self._metrics_scroll = QScrollArea()
        self._metrics_scroll.setWidgetResizable(True)
        self._metrics_container = QWidget()
        self._metrics_layout = QVBoxLayout(self._metrics_container)
        self._metrics_layout.setContentsMargins(2, 2, 2, 2)
        self._metrics_layout.setSpacing(2)
        self._metrics_scroll.setWidget(self._metrics_container)
        metrics_layout.addWidget(self._metrics_scroll, 3)

        # Окно MA + сброс
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Окно MA:"))
        self._window_spin = QSpinBox()
        self._window_spin.setRange(1, 10)
        self._window_spin.setValue(3)
        bottom_row.addWidget(self._window_spin)
        bottom_row.addStretch()
        self._reset_btn = QPushButton("Сброс")
        self._reset_btn.setToolTip("Снять все выбранные показатели")
        bottom_row.addWidget(self._reset_btn)
        metrics_layout.addLayout(bottom_row)

        # Разделитель
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        metrics_layout.addWidget(separator)

        # Пресеты
        metrics_layout.addWidget(QLabel("Пресеты:"))
        self._presets_list = QListWidget()
        self._presets_list.setToolTip("Кликните, чтобы применить набор показателей")
        metrics_layout.addWidget(self._presets_list, 1)

        preset_btn_row = QHBoxLayout()
        self._save_preset_btn = QPushButton("💾 Сохранить")
        self._save_preset_btn.setToolTip("Сохранить выбранные показатели как пресет")
        self._delete_preset_btn = QPushButton("🗑 Удалить")
        preset_btn_row.addWidget(self._save_preset_btn)
        preset_btn_row.addWidget(self._delete_preset_btn)
        metrics_layout.addLayout(preset_btn_row)

        # --- Правая часть: график ---
        self._figure = Figure(figsize=(8, 8))
        self._canvas = FigureCanvas(self._figure)

        self._splitter.addWidget(companies_widget)
        self._splitter.addWidget(metrics_widget)
        self._splitter.addWidget(self._canvas)

        self._splitter.setSizes([LEFT_COL_WIDTH, LEFT_COL_WIDTH + 40, 600])
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, False)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setStretchFactor(2, 1)

        root.addWidget(self._splitter, 1)

        # === Нижняя строка: статус + папка кэша ===
        status_row = QHBoxLayout()
        self._status_label = QLabel("Данные не загружены")
        self._status_label.setStyleSheet("color: gray;")
        status_row.addWidget(self._status_label, 1)

        self._open_cache_btn = QPushButton("📂 Папка кэша")
        self._open_cache_btn.setToolTip(f"Открыть папку: {CACHE_DIR}")
        status_row.addWidget(self._open_cache_btn)
        root.addLayout(status_row)

        # Таймер debounce
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(REDRAW_DEBOUNCE_MS)
        self._redraw_timer.timeout.connect(self._render_charts)

    def _connect_signals(self):
        self._generate_btn.clicked.connect(self._on_generate)
        self._reset_btn.clicked.connect(self._on_reset_metrics)
        self._company_search.textChanged.connect(self._on_company_search)
        self._metric_search.textChanged.connect(self._on_metric_search)
        self._company_table.itemSelectionChanged.connect(self._schedule_redraw)
        self._window_spin.valueChanged.connect(self._schedule_redraw)
        self._open_cache_btn.clicked.connect(self._open_cache_folder)
        # Пресеты
        self._save_preset_btn.clicked.connect(self._on_save_preset)
        self._delete_preset_btn.clicked.connect(self._on_delete_preset)
        self._presets_list.itemClicked.connect(self._on_preset_selected)
        self._alloc_only_checkbox.toggled.connect(self._on_alloc_toggle)
        self._alloc_selector.pathChanged.connect(self._on_alloc_path_changed)

    # ───────────────────────────────────────────────────────────── Данные
    def _try_load_cache(self):
        if CACHE_FILE.exists():
            try:
                df = pd.read_csv(CACHE_FILE)
                self._apply_data(df)
                self._status_label.setText(
                    f"Загружено из кэша: {df['ticker'].nunique()} тикеров"
                )
            except Exception as e:
                self._status_label.setText(f"Ошибка чтения кэша: {e}")

    def _on_generate(self):
        ff = self._ff_selector.path()
        ir = self._ir_selector.path()
        sl = self._sl_selector.path()

        if not all([ff, ir, sl]):
            QMessageBox.warning(
                self, "Не заполнены пути",
                "Укажите все три пути: free-float, IR рейтинг, папку SmartLab.",
            )
            return

        errors = []
        if not self._ff_selector.is_valid():
            errors.append("Free-float: файл не найден")
        if not self._ir_selector.is_valid():
            errors.append("IR рейтинг: файл не найден")
        if not Path(sl).is_dir():
            errors.append("SmartLab: папка не найдена")

        if errors:
            QMessageBox.warning(self, "Проверьте пути", "\n".join(errors))
            return

        self._set_busy(True, "Формирование данных (MOEX + парсинг CSV)...")
        self._worker = AnalysisDataWorker(ff, ir, sl, CACHE_FILE)
        self._worker.success.connect(self._on_data_ready)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_data_ready(self, df: pd.DataFrame):
        self._apply_data(df)
        self._status_label.setText(
            f"Данные сформированы: {df['ticker'].nunique()} тикеров, "
            f"{len(df)} записей"
        )

    def _apply_data(self, df: pd.DataFrame):
        self._df = df
        self._populate_companies(df)
        self._populate_metrics(df)

    def _populate_companies(self, df: pd.DataFrame):
        smartlab_tickers = sorted(
            df[df['type'] == 'smartlab']['ticker'].dropna().unique()
        )
        names_map = {}
        name_rows = df[df['indicator'] == 'name'].drop_duplicates(subset=['ticker'])
        for _, row in name_rows.iterrows():
            names_map[row['ticker']] = row['value']

        self._company_table.setRowCount(len(smartlab_tickers))
        for i, ticker in enumerate(smartlab_tickers):
            name = names_map.get(ticker, "")
            self._company_table.setItem(i, 0, QTableWidgetItem(ticker))
            self._company_table.setItem(i, 1, QTableWidgetItem(str(name)))
        self._apply_company_filter()

    def _populate_metrics(self, df: pd.DataFrame):
        while self._metrics_layout.count():
            item = self._metrics_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._metric_checkboxes.clear()

        chartable = df[
            (df['type'] == 'smartlab')
            & (df['year'].notna())
            & (~df['indicator'].isin(NON_CHART_INDICATORS))
        ]['indicator'].unique()

        for metric in sorted(chartable):
            cb = QCheckBox(metric)
            cb.stateChanged.connect(self._on_metric_toggled)
            self._metrics_layout.addWidget(cb)
            self._metric_checkboxes[metric] = cb

        self._metrics_layout.addStretch()

    # ───────────────────────────────────────────────────────────── Показатели
    def _on_metric_toggled(self):
        """При изменении чекбокса: пересортировать и перерисовать."""
        self._reorder_metrics()
        self._schedule_redraw()

    def _reorder_metrics(self):
        """Переносит отмеченные показатели наверх, сохраняя алфавитный порядок в группах."""
        ordered = sorted(
            self._metric_checkboxes.values(),
            key=lambda cb: (not cb.isChecked(), cb.text()),
        )
        # Убираем всё из layout (виджеты не удаляются)
        while self._metrics_layout.count():
            self._metrics_layout.takeAt(0)
        # Добавляем в новом порядке
        for cb in ordered:
            self._metrics_layout.addWidget(cb)
        self._metrics_layout.addStretch()

    def _on_metric_search(self, text: str):
        text = text.lower().strip()
        for metric, cb in self._metric_checkboxes.items():
            cb.setVisible(not text or text in metric.lower())

    def _on_reset_metrics(self):
        for cb in self._metric_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._reorder_metrics()
        self._figure.clear()
        self._canvas.draw()

    # ───────────────────────────────────────────────────────────── Пресеты
    def _load_presets(self) -> dict:
        if PRESETS_FILE.exists():
            try:
                with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_presets(self, presets: dict):
        PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)

    def _populate_presets_list(self):
        self._presets_list.clear()
        presets = self._load_presets()
        for name in sorted(presets.keys()):
            self._presets_list.addItem(name)

    def _on_save_preset(self):
        selected = [m for m, cb in self._metric_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(
                self, "Нет показателей",
                "Выберите хотя бы один показатель для сохранения пресета.",
            )
            return

        name, ok = QInputDialog.getText(self, "Сохранить пресет", "Название пресета:")
        if not ok or not name.strip():
            return
        name = name.strip()

        presets = self._load_presets()
        if name in presets:
            reply = QMessageBox.question(
                self, "Пресет существует",
                f"Пресет '{name}' уже существует. Перезаписать?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        presets[name] = selected
        self._save_presets(presets)
        self._populate_presets_list()

        items = self._presets_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self._presets_list.setCurrentItem(items[0])
        self._status_label.setText(f"Пресет '{name}' сохранён")

    def _on_preset_selected(self, item: QTableWidgetItem):
        presets = self._load_presets()
        name = item.text()
        if name not in presets:
            return

        metric_names = set(presets[name])
        for metric, cb in self._metric_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(metric in metric_names)
            cb.blockSignals(False)

        self._reorder_metrics()
        self._schedule_redraw()
        self._status_label.setText(f"Применён пресет '{name}'")

    def _on_delete_preset(self):
        current = self._presets_list.currentItem()
        if not current:
            QMessageBox.information(self, "Удаление пресета", "Выберите пресет для удаления.")
            return
        name = current.text()
        presets = self._load_presets()
        if name in presets:
            del presets[name]
            self._save_presets(presets)
            self._populate_presets_list()
            self._status_label.setText(f"Пресет '{name}' удалён")

    # ───────────────────────────────────────────────────────────── Кэш
    def _open_cache_folder(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(CACHE_DIR)))

    # ───────────────────────────────────────────────────────────── Поиск компаний
    def _on_company_search(self, text: str):
        """Точка входа поиска — делегирует общему фильтру."""
        self._apply_company_filter()

    def _apply_company_filter(self):
        """Комбинированный фильтр: поиск + тикеры из распределения."""
        text = self._company_search.text().lower().strip()
        alloc_only = self._alloc_only_checkbox.isChecked()
        alloc_tickers = self._alloc_tickers if alloc_only else None

        for row in range(self._company_table.rowCount()):
            ticker_item = self._company_table.item(row, 0)
            name_item = self._company_table.item(row, 1)
            ticker = ticker_item.text() if ticker_item else ""
            name = name_item.text().lower() if name_item else ""

            search_match = not text or text in ticker.lower() or text in name
            alloc_match = (alloc_tickers is None) or (ticker in alloc_tickers)

            self._company_table.setRowHidden(row, not (search_match and alloc_match))

    # ───────────────────────────────────────────────────────────── Графики
    def _schedule_redraw(self):
        self._redraw_timer.start()

    def _get_selected_ticker(self) -> str | None:
        selected_rows = self._company_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self._company_table.item(row, 0)
        return item.text() if item else None

    def _render_charts(self):
        if self._df is None:
            return

        ticker = self._get_selected_ticker()
        metrics = [m for m, cb in self._metric_checkboxes.items() if cb.isChecked()]

        if not ticker or not metrics:
            return

        window = self._window_spin.value()
        self._figure.clear()

        n = len(metrics)
        if n == 1:
            ax = self._figure.add_subplot(111)
            result = plot_one_chart(
                self._df, ticker=ticker, title=metrics[0],
                window=window, axes=ax, show=False,
            )
            if result is None:
                ax.text(0.5, 0.5, f"Нет данных: {ticker} / {metrics[0]}",
                        ha='center', va='center', transform=ax.transAxes)
        else:
            cols = min(n, 2)
            rows = math.ceil(n / cols)
            for i, metric in enumerate(metrics):
                ax = self._figure.add_subplot(rows, cols, i + 1)
                result = plot_one_chart(
                    self._df, ticker=ticker, title=metric,
                    window=window, axes=ax, show=False,
                )
                if result is None:
                    ax.text(0.5, 0.5, "Нет данных",
                            ha='center', va='center', transform=ax.transAxes)

        name_rows = self._df[
            (self._df['ticker'] == ticker) & (self._df['indicator'] == 'name')
        ]
        title = name_rows['value'].iloc[0] if not name_rows.empty else ticker
        self._figure.suptitle(f"{title} ({ticker})", fontsize=13, fontweight='bold')
        self._figure.tight_layout(rect=(0, 0, 1, 0.96))
        self._canvas.draw()

    # ───────────────────────────────────────────────────────────── Служебное
    def _on_worker_error(self, message: str):
        self._status_label.setText("Ошибка")
        QMessageBox.critical(self, "Ошибка", message)

    def _on_worker_finished(self):
        self._set_busy(False)
        if self._worker:
            self._worker.deleteLater()
        self._worker = None

    def _set_busy(self, busy: bool, status: str = None):
        self._generate_btn.setEnabled(not busy)
        if status:
            self._status_label.setText(status)

    def set_log_panel(self, log_panel):
        pass

    def _on_alloc_toggle(self, checked: bool):
        """При включении фильтра без файла — открывает диалог выбора."""
        if checked:
            path = self._alloc_selector.path()
            if not path or not Path(path).exists():
                from PyQt6.QtWidgets import QFileDialog
                new_path, _ = QFileDialog.getOpenFileName(
                    self, "Выберите таблицу распределения",
                    path or str(Path.home()),
                    "Excel файлы (*.xlsx *.xls);;Все файлы (*)",
                )
                if not new_path:
                    # Отмена — снимаем чекбокс без рекурсии сигналов
                    self._alloc_only_checkbox.blockSignals(True)
                    self._alloc_only_checkbox.setChecked(False)
                    self._alloc_only_checkbox.blockSignals(False)
                    return
                self._alloc_selector.set_path(new_path)
                # set_path → pathChanged → загрузка + фильтр
                return
            self._load_alloc_tickers()
        self._apply_company_filter()

    def _on_alloc_path_changed(self, path: str):
        """При смене пути перечитываем тикеры, если фильтр активен."""
        if self._alloc_only_checkbox.isChecked():
            self._load_alloc_tickers()
            self._apply_company_filter()

    def _load_alloc_tickers(self):
        """Читает таблицу распределения и извлекает уникальные тикеры."""
        path = self._alloc_selector.path()
        self._alloc_tickers = set()

        if not path or not Path(path).exists():
            self._status_label.setText("Файл распределения не найден")
            return

        try:
            from invest_toolkit.io import allocatin_table
            at = allocatin_table(path)
            self._alloc_tickers = set(at['ticker'].dropna().astype(str).unique())
            self._status_label.setText(
                f"Тикеров в распределении: {len(self._alloc_tickers)}"
            )
        except Exception as e:
            self._status_label.setText(f"Ошибка таблицы распределения: {e}")