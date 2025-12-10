import logging
import os
from typing import Optional


class Logger:
    """
    Фасад для удобного статического логирования без необходимости создания экземпляров.

    Использует модуль `logging` и автоматически инициализирует файловый обработчик
    при первом вызове любого метода логирования, если не был инициализирован ранее.
    По умолчанию логи записываются в `logs/app.log` относительно корня проекта.

    Класс поддерживает настройку пути к файлу и уровня логирования через метод `configure`.
    Также предоставляет метод `clear` для безопасной очистки лог-файла даже под Windows.

    Example:
        >>> Logger.info("Приложение запущено")
        >>> Logger.error("Произошла ошибка", name="db")
    """
    _initialized: bool = False
    _log_file: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs/app.log")
    _level: int = logging.DEBUG
    _logger: Optional[logging.Logger] = None

    @classmethod
    def _ensure_initialized(cls) -> None:
        """
        Гарантирует, что логгер инициализирован ровно один раз.

        Создаёт директорию для логов, настраивает форматтер и файловый обработчик,
        а также отключает распространение логов выше по иерархии (чтобы избежать дублирования).

        :raises OSError: Если не удаётся создать директорию для логов.
        """
        if cls._initialized:
            return

        log_dir = os.path.dirname(cls._log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(cls._log_file, encoding='utf-8')
        file_handler.setLevel(cls._level)
        file_handler.setFormatter(formatter)

        cls._logger = logging.getLogger('logger')
        if cls._logger.hasHandlers():
            cls._logger.handlers.clear()
        cls._logger.setLevel(cls._level)
        cls._logger.addHandler(file_handler)
        cls._logger.propagate = False  # избегаем дублирования

        cls._initialized = True


    @classmethod
    def configure(cls, log_file: str = "app.log", level: int = logging.INFO) -> None:
        """
        Настраивает параметры логирования до первого использования.

        Сбрасывает флаг инициализации, чтобы при следующем вызове логирования
        применить новые настройки.

        :param log_file: Абсолютный или относительный путь к файлу лога.Будет преобразован в абсолютный путь.
        :param level: Уровень логирования (например, `logging.DEBUG`, `logging.INFO`).
        :raises ValueError: Если `log_file` — пустая строка или не строка.
        :raises TypeError: Если `level` не является целым числом.
        """
        if not isinstance(log_file, str) or not log_file.strip():
            raise ValueError("log_file must be a non-empty string.")
        if not isinstance(level, int):
            raise TypeError("level must be an integer.")
        cls._log_file = os.path.abspath(log_file)
        cls._level = level
        cls._initialized = False  # сброс для переинициализации


    @classmethod
    def clear(cls) -> None:
        """
        Безопасно очищает содержимое лог-файла.

        Если логгер уже инициализирован, закрывает все файловые обработчики,
        чтобы избежать блокировки файла (особенно актуально в Windows),
        затем пересоздаёт файл с пустым содержимым.

        :raises OSError: Если не удаётся создать директорию или очистить файл.
        """
        if cls._initialized and cls._logger is not None:
            # Закрываем все обработчики файла
            for handler in cls._logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
            cls._logger.handlers.clear()
            cls._initialized = False

        # Очищаем файл: создаём заново или обнуляем
        log_dir = os.path.dirname(cls._log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(cls._log_file, 'w', encoding='utf-8') as f:
            f.write('')  # просто обнуляем

    @classmethod
    def _get_logger(cls, name: str) -> logging.Logger:
        """
        Возвращает дочерний логгер с заданным именем.

        Гарантирует инициализацию основного логгера при необходимости.

        :param name: Имя дочернего логгера (отображается в поле `%(name)s`).
        :return: Экземпляр `logging.Logger`.
        """
        cls._ensure_initialized()
        return cls._logger.getChild(name)  # создаёт дочерний логгер  

    @classmethod
    def debug(cls, name:str = 'log', message:str = '') -> None:
        """
        Записывает сообщение уровня INFO.

        :param name: Имя подсистемы или модуля (отображается в логе).
        :param message: Текст сообщения.
        """
        cls._ensure_initialized()
        cls._get_logger(name).debug(message, stacklevel=2)

    @classmethod
    def info(cls, name:str = 'log', message:str = '') -> None:
        """
        Записывает сообщение уровня WARNING.

        :param name: Имя подсистемы или модуля (отображается в логе).
        :param message: Текст сообщения.
        """
        cls._ensure_initialized()
        cls._get_logger(name).info(message, stacklevel=2)

    @classmethod
    def warning(cls, name:str = 'log', message:str = '') -> None:
        """
        Записывает сообщение уровня WARNING.

        :param name: Имя подсистемы или модуля (отображается в логе).
        :param message: Текст сообщения.
        """
        cls._ensure_initialized()
        cls._get_logger(name).warning(message, stacklevel=2)

    @classmethod
    def error(cls, name:str = 'log', message:str = '') -> None:
        """
        Записывает сообщение уровня ERROR.

        :param name: Имя подсистемы или модуля (отображается в логе).
        :param message: Текст сообщения.
        """
        cls._ensure_initialized()
        cls._get_logger(name).error(message, stacklevel=2)

    @classmethod
    def critical(cls, name:str = 'log', message:str = '') -> None:
        """
        Записывает сообщение уровня CRITICAL.

        :param name: Имя подсистемы или модуля (отображается в логе).
        :param message: Текст сообщения.
        """
        cls._ensure_initialized()
        cls._get_logger(name).critical(message, stacklevel=2)

if __name__ == '__main__':
    def run():
        Logger.info('as', "Тест логирования")
    run()
