import pandas as pd


class ReportRegistry:
    """
    Реестр для накопления и хранения брокерских отчётов (DataFrame-ов).

    Предназначен для агрегации результатов парсинга (например, `balance_report`)
    из нескольких источников или периодов. Поддерживает только добавление —
    без валидации, дедупликации или метаданных.

    Атрибуты:
        report_list: Список DataFrame-ов, добавленных через метод `add`.
                     Порядок сохраняется.
    """
    def __init__(self):
        """Инициализирует пустой реестр отчётов."""
        self.report_list: list[pd.DataFrame] = list()
        
    def add(self, df):
        """Добавляет DataFrame в реестр.

        :param df: Отчёт (например, результат `BrokerParser.get_balance_report_df()`).
        :type df: pd.DataFrame

        .. note::
            Метод не проверяет:
            - не является ли `df` пустым,
            - соответствует ли структура ожидаемой,
            - не добавлен ли уже идентичный отчёт.

            Просто добавляет ссылку в `self.report_list`.
        """
        self.report_list.append(df)

