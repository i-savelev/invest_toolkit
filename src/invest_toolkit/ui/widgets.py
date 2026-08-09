from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog,
    QMenu, QCheckBox, QWidgetAction,
)


class FileSelector(QWidget):
    """Поле пути + кнопка 'Обзор' для выбора файла или папки."""

    pathChanged = pyqtSignal(str)

    def __init__(self, caption="Выберите файл", file_filter="",
                 directory=False, parent=None):
        super().__init__(parent)
        self._caption = caption
        self._filter = file_filter
        self._directory = directory

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Путь не выбран...")
        self._edit.setClearButtonEnabled(True)
        self._edit.textChanged.connect(self.pathChanged)

        self._btn = QPushButton("Обзор...")
        self._btn.setFixedWidth(90)
        self._btn.clicked.connect(self._browse)

        layout.addWidget(self._edit, 1)
        layout.addWidget(self._btn)

    def _browse(self):
        start = self._edit.text() or str(Path.home())
        if self._directory:
            path = QFileDialog.getExistingDirectory(self, self._caption, start)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, self._caption, start, self._filter
            )
        if path:
            self._edit.setText(path)

    def path(self) -> str:
        return self._edit.text().strip()

    def set_path(self, path: str):
        self._edit.setText(path)

    def is_valid(self) -> bool:
        p = self.path()
        return bool(p) and Path(p).exists()


class CheckableComboBox(QPushButton):
    """Кнопка, открывающая меню с чекбоксами для множественного выбора."""

    selectionChanged = pyqtSignal()

    def __init__(self, placeholder="Не выбрано", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._options: list[str] = []
        self._checked: set[str] = set()
        self.setMinimumWidth(180)
        self.setText(placeholder)
        self.clicked.connect(self._show_menu)

    def set_options(self, options, selected=None):
        """Задаёт список опций. `selected` — что отметить сразу."""
        self._options = sorted({str(o) for o in options if str(o)})
        self._checked = set(selected or []) & set(self._options)
        self._update_text()

    def get_selected(self) -> list[str]:
        return [o for o in self._options if o in self._checked]

    def set_selected(self, items):
        self._checked = set(items) & set(self._options)
        self._update_text()

    def clear(self):
        self._options = []
        self._checked = set()
        self._update_text()

    def _show_menu(self):
        if not self._options:
            return
        menu = QMenu(self)
        for option in self._options:
            cb = QCheckBox(option, menu)
            cb.setChecked(option in self._checked)
            cb.toggled.connect(
                lambda checked, opt=option: self._on_toggle(opt, checked)
            )
            action = QWidgetAction(menu)
            action.setDefaultWidget(cb)
            menu.addAction(action)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _on_toggle(self, option, checked):
        if checked:
            self._checked.add(option)
        else:
            self._checked.discard(option)
        self._update_text()
        self.selectionChanged.emit()

    def _update_text(self):
        selected = self.get_selected()
        self.setText(", ".join(selected) if selected else self._placeholder)