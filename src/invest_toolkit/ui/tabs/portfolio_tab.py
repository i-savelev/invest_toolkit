from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QSpinBox, QCheckBox, QGroupBox, QMessageBox,
)

from invest_toolkit.ui.widgets import FileSelector, CheckableComboBox
from invest_toolkit.ui.workers import LoadTickersWorker, RunReportWorker

DEFAULT_TRACKED = ("LQDT", "SBMM")


class PortfolioTab(QWidget):
    """Вкладка формирования отчёта по портфелю и ребалансировки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_panel = None
        self._tickers_loaded = False
        self._worker = None

        self._build_ui()
        self._connect_signals()
        self._update_controls_state()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # --- Исходные файлы ---
        files_group = QGroupBox("Исходные данные")
        files_form = QFormLayout(files_group)
        files_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._sber_selector = FileSelector(
            caption="Выберите отчёт Сбербанка",
            file_filter="HTML файлы (*.html *.HTML *.htm);;Все файлы (*)",
        )
        self._vtb_selector = FileSelector(
            caption="Выберите отчёт ВТБ",
            file_filter="Excel файлы (*.xlsx *.xls);;Все файлы (*)",
        )
        self._alloc_selector = FileSelector(
            caption="Выберите таблицу распределения",
            file_filter="Excel файлы (*.xlsx *.xls);;Все файлы (*)",
        )
        self._save_selector = FileSelector(
            caption="Выберите папку для сохранения отчёта",
            directory=True,
        )

        files_form.addRow("Отчёт Сбербанка:", self._sber_selector)
        files_form.addRow("Отчёт ВТБ:", self._vtb_selector)
        files_form.addRow("Распределение:", self._alloc_selector)
        files_form.addRow("Сохранить отчёт в:", self._save_selector)
        root.addWidget(files_group)

        # --- Параметры ---
        params_group = QGroupBox("Параметры ребалансировки")
        params_form = QFormLayout(params_group)
        params_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._deposit_spin = QSpinBox()
        self._deposit_spin.setRange(0, 1_000_000_000)
        self._deposit_spin.setSingleStep(1000)
        self._deposit_spin.setSuffix(" ₽")

        self._grouping_combo = CheckableComboBox("Тикеры для группировки...")
        self._sell_tickers_combo = CheckableComboBox("Тикеры для продажи...")

        self._sell_checkbox = QCheckBox("Разрешить продажи")
        self._sell_checkbox.setChecked(True)

        params_form.addRow("Депозит:", self._deposit_spin)
        params_form.addRow("Группировка тикеров:", self._grouping_combo)
        params_form.addRow("Тикеры для продажи:", self._sell_tickers_combo)
        params_form.addRow("", self._sell_checkbox)
        root.addWidget(params_group)

        # --- Кнопки ---
        buttons = QHBoxLayout()
        self._load_tickers_btn = QPushButton("🔄 Загрузить тикеры")
        self._run_report_btn = QPushButton("▶ Сформировать отчёт")
        self._run_report_btn.setStyleSheet("font-weight: bold;")
        buttons.addWidget(self._load_tickers_btn)
        buttons.addWidget(self._run_report_btn)
        buttons.addStretch()
        root.addLayout(buttons)

        # --- Статус ---
        self._status_label = QLabel("Готов к работе")
        self._status_label.setStyleSheet("color: gray;")
        root.addWidget(self._status_label)

        root.addStretch()

    def _connect_signals(self):
        self._load_tickers_btn.clicked.connect(self._on_load_tickers)
        self._run_report_btn.clicked.connect(self._on_run_report)
        self._sell_checkbox.toggled.connect(self._update_controls_state)

    def _update_controls_state(self):
        """Активирует комбо только после загрузки тикеров."""
        self._grouping_combo.setEnabled(self._tickers_loaded)
        sell_enabled = self._tickers_loaded and self._sell_checkbox.isChecked()
        self._sell_tickers_combo.setEnabled(sell_enabled)

    # ------------------------------------------------------- Загрузка тикеров
    def _on_load_tickers(self):
        sber = self._sber_selector.path()
        vtb = self._vtb_selector.path()
        alloc = self._alloc_selector.path()

        if not (sber and vtb and alloc):
            QMessageBox.warning(
                self, "Не заполнены пути",
                "Укажите отчёт Сбербанка, отчёт ВТБ и таблицу распределения.",
            )
            return

        missing = [
            name for name, sel in (
                ("Отчёт Сбербанка", self._sber_selector),
                ("Отчёт ВТБ", self._vtb_selector),
                ("Таблица распределения", self._alloc_selector),
            ) if not sel.is_valid()
        ]
        if missing:
            QMessageBox.warning(
                self, "Файлы не найдены",
                "Не найдены файлы:\n" + "\n".join(missing),
            )
            return

        self._set_busy(True, "Загрузка тикеров (MOEX + парсинг)...")
        self._worker = LoadTickersWorker(sber, vtb, alloc)
        self._worker.success.connect(self._on_tickers_loaded)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_tickers_loaded(self, tickers):
        self._tickers_loaded = True
        defaults = [t for t in DEFAULT_TRACKED if t in tickers]
        self._grouping_combo.set_options(tickers, selected=defaults)
        self._sell_tickers_combo.set_options(tickers, selected=defaults)
        self._update_controls_state()
        self._set_status(f"Загружено тикеров: {len(tickers)}")

    # ------------------------------------------------------- Запуск отчёта
    def _on_run_report(self):
        params = self._collect_params()
        errors = self._validate_params(params)
        if errors:
            QMessageBox.warning(self, "Проверьте параметры", "\n".join(errors))
            return

        self._set_busy(True, "Формирование отчёта...")
        self._worker = RunReportWorker(params)
        self._worker.success.connect(self._on_report_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _collect_params(self):
        return {
            "report_path_sber": self._sber_selector.path(),
            "report_path_vtb": self._vtb_selector.path(),
            "allocation_path": self._alloc_selector.path(),
            "deposit": float(self._deposit_spin.value()),
            "grouping_tickers": self._grouping_combo.get_selected(),
            "sell": self._sell_checkbox.isChecked(),
            "allow_sell_tickers": self._sell_tickers_combo.get_selected(),
            "report_save_path": self._save_selector.path(),
        }

    def _validate_params(self, params):
        errors = []
        for label, key in (
            ("Отчёт Сбербанка", "report_path_sber"),
            ("Отчёт ВТБ", "report_path_vtb"),
            ("Таблица распределения", "allocation_path"),
        ):
            if not params[key] or not Path(params[key]).exists():
                errors.append(f"{label}: файл не найден")
        if not params["report_save_path"]:
            errors.append("Не указана папка для сохранения отчёта")
        return errors

    def _on_report_done(self, save_path):
        self._set_status(f"Отчёт сохранён в: {save_path}")
        QMessageBox.information(
            self, "Готово",
            f"Отчёт успешно сформирован.\nСохранён в: {save_path}",
        )

    # ------------------------------------------------------- Служебное
    def _on_worker_error(self, message):
        self._set_status("Ошибка выполнения")
        QMessageBox.critical(self, "Ошибка", message)

    def _on_worker_finished(self):
        self._set_busy(False)
        if self._worker:
            self._worker.deleteLater()
        self._worker = None

    def _set_busy(self, busy, status=None):
        self._load_tickers_btn.setEnabled(not busy)
        self._run_report_btn.setEnabled(not busy)
        if status:
            self._set_status(status)

    def _set_status(self, text):
        self._status_label.setText(text)

    def set_log_panel(self, log_panel):
        """Совместимость с MainWindow (панель лога)."""
        self._log_panel = log_panel