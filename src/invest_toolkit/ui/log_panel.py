import queue
import logging

from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QVBoxLayout, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QFontDatabase, QTextCursor

from invest_toolkit.utils.logger import Logger


class _QueueHandler(logging.Handler):
    """Перехватывает стандартные log-сообщения и кладёт в очередь."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class LogPanel(QWidget):
    """Панель лога как обычная вкладка."""

    POLL_INTERVAL_MS = 100
    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)

        self._queue: queue.Queue = queue.Queue()

        # Подключаем очередь к логгеру
        Logger.attach_gui_queue(self._queue)

        # Подключаем QueueHandler для стандартных log.info/error/etc.
        handler = _QueueHandler(self._queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logging.getLogger("log").addHandler(handler)

        # UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Панель инструментов
        toolbar = QHBoxLayout()
        self._btn_clear = QPushButton("Очистить")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.clicked.connect(self.clear_log)
        toolbar.addWidget(self._btn_clear)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Текстовое поле лога
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)

        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSize(9)
        self._text_edit.setFont(mono_font)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._text_edit.setStyleSheet(
            "QTextEdit { "
            "  background-color: #1e1e2e; "
            "  color: #cdd6f4; "
            "  font-family: 'Consolas', 'Courier New', 'SF Mono', 'Menlo', monospace !important; "
            "}"
        )
        layout.addWidget(self._text_edit)

        # Таймер опроса очереди
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_queue)
        self._timer.start(self.POLL_INTERVAL_MS)

    def _poll_queue(self):
        lines = []
        while not self._queue.empty():
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if lines:
            self._text_edit.append("\n".join(lines))
            if self._text_edit.document().blockCount() > self.MAX_LINES:
                self._trim_lines()
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._text_edit.setTextCursor(cursor)

    def _trim_lines(self):
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        excess = self._text_edit.document().blockCount() - self.MAX_LINES
        for _ in range(excess):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor
            )
        cursor.removeSelectedText()
        cursor.deleteChar()

    def clear_log(self):
        self._text_edit.clear()

    def append_message(self, message: str):
        self._queue.put(message)