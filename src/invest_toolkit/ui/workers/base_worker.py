from PyQt6.QtCore import QThread, pyqtSignal


class BaseWorker(QThread):
    """Базовый фоновый воркер. Наследники реализуют do_work()."""

    success = pyqtSignal(object)   # результат работы
    error = pyqtSignal(str)        # текст ошибки

    def run(self):
        try:
            result = self.do_work()
            self.success.emit(result)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

    def do_work(self):
        raise NotImplementedError