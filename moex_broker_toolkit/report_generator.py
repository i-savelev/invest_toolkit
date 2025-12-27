from .report_strategy import ReportStrategy
import pandas as pd
from pathlib import Path


class ReportGenerator:
    """
    Генератор отчётов, реализующий паттерн *Strategy*.

    Позволяет:
    - выбирать формат вывода (Markdown, HTML и др.) через стратегию,
    - генерировать отчёт,
    - сохранять его в файл.

    Отделяет *что* генерировать (данные, логика в `ReportStrategy`) от *как* генерировать (формат).

    Атрибуты:
        _strategy: Текущая стратегия форматирования.
        report: Последний сгенерированный отчёт (строка). Инициализируется пустой строкой.
    """

    def __init__(self, strategy: ReportStrategy) -> None:
        """
        Инициализирует генератор с заданной стратегией.

        :param strategy: Объект, реализующий `ReportStrategy`.
        :type strategy: ReportStrategy

        :raises TypeError: Если `strategy` не является экземпляром `ReportStrategy`.
        """
        if not isinstance(strategy, ReportStrategy):
            raise TypeError("Стратегия должна быть экземпляром ReportStrategy.")
        self._strategy = strategy
        self.report:str = ''

    def generate_report(self) -> str:
        """
        Генерирует отчёт с использованием текущей стратегии.

        Результат кэшируется в `self.report`.

        :returns: Сформированный отчёт в виде строки.
        :rtype: str

        :raises NotImplementedError: Если `strategy.generate()` не реализован.
        :raises ValueError / KeyError / OSError: В зависимости от реализации стратегии.
        """
        self.report = self._strategy.generate()
        return self.report

    def set_strategy(self, strategy: ReportStrategy) -> None:
        """
        Изменяет текущую стратегию форматирования.

        :param strategy: Новая стратегия.
        :type strategy: ReportStrategy

        :raises TypeError: Если `strategy` не реализует `ReportStrategy`.
        """
        if not isinstance(strategy, ReportStrategy):
            raise TypeError("Стратегия должна быть экземпляром ReportStrategy.")
        self._strategy = strategy

    def save_report(self, path:str):
        """
        Сохраняет последний сгенерированный отчёт в файл.

        Перед записью создаются родительские директории (закомментировано в оригинале,
        но поведение сохранено — при необходимости можно раскомментировать).

        :param path: Путь к файлу назначения (например, `"./reports/report.md"`).
        :type path: str

        :raises TypeError: Если `path` не является строкой.
        :raises ValueError: Если `self.report` пуст (отчёт не генерировался).
        :raises OSError: При ошибках файловой системы (нет прав, диск переполнен и т.д.).
        """
        if not isinstance(path, str):
            raise TypeError("Путь к файлу должен быть строкой.")

        if self.report is None:
            raise ValueError(
                "Отчет еще не был сгенерирован. Вызовите generate_report() перед save_report()."
            )

        file_path = Path(path)
        try:
            # Создаем родительские директории, если их нет
            # file_path.parent.mkdir(parents=True, exist_ok=True)
            # # Записываем отчет в файл
            file_path.write_text(self.report, encoding="utf-8")
        except OSError as e:
            raise OSError(f"Не удалось сохранить отчет по пути '{path}': {e}") from e
