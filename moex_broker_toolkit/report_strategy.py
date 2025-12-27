from abc import ABC, abstractmethod
import pandas as pd

class ReportStrategy(ABC):
    """
    Абстрактная стратегия генерации отчёта.

    Определяет общий интерфейс для всех форматов отчётов (Markdown, HTML, Excel и др.).
    Конкретные реализации (например, `MdReportStrategy`) обязаны реализовать метод `generate()`.

    .. note::
        Хотя в текущей сигнатуре `generate()` не принимает параметров напрямую,
        подразумевается, что данные передаются через конструктор (например, `TargetAllocator`,
        `DataFrame`, шаблон и т.д.).

    Пример использования:
        strategy = MdReportStrategy(allocator, "template.md")
        report = strategy.generate()
        print(report)
    """

    @abstractmethod
    def generate(self) -> str:
        """
        Генерирует отчёт в конкретном формате.

        Конкретная реализация должна:
        - использовать внутренние данные (переданные в `__init__`),
        - возвращать строку (например, Markdown, HTML),
        - выбрасывать исключения при ошибках форматирования или отсутствии данных.

        :returns: Готовый отчёт в виде строки.
        :rtype: str

        :raises NotImplementedError: Если метод не переопределён в подклассе.
        :raises ValueError: При некорректных входных данных (реализация-зависимо).
        :raises KeyError / AttributeError: При отсутствии ожидаемых полей в исходных данных.
        """
        pass