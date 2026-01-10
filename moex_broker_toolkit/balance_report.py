from .report_registry import ReportRegistry
import pandas as pd
from fin_analysis.utils import moex_api_utils as moex
from typing import Optional
from .distribution_table import DistributionTable

class BalanceReport:
    """
    Формирует итоговый балансовый отчёт путём объединения брокерских отчётов и целевого распределения.

    Агрегирует:
    - реальные позиции из `ReportRegistry` (например, ВТБ + Сбер),
    - целевые доли позиций из `DistributionTable`.

    После объединения:
    - группирует по тикеру,
    - суммирует количество, берёт первое совпадение по `name` и `Размер лота`,
    - запрашивает текущую цену через MOEX API,
    - рассчитывает стоимость и долю в портфеле (%).

    .. note::
        Класс предполагает, что:
        - все входные DataFrame содержат колонки: `'ticker'`, `'Кол-во (шт)'`, `'Размер лота'`, `'name'`,
        - `DistributionTable.distribution_table` уже сформирован (вызван `.get_table()`).

    Атрибуты:
        report_registry: Реестр брокерских отчётов.
        balance_report: Итоговый DataFrame с актуальным портфелем и его стоимостью.
        dt: Экземпляр `DistributionTable` с распределением (целевыми/виртуальными позициями).
    """
    def __init__(
            self,
            report_registry: ReportRegistry,
            distribution_table: DistributionTable,
            ):
        """
        Инициализирует балансовый отчёт.

        :param report_registry: Накопленные отчёты брокеров.
        :param distribution_table: Целевое распределение (уже обработанное).
        """
        self.report_registry = report_registry
        self.balance_report: pd.DataFrame 
        self.dt: DistributionTable = distribution_table

    def get_balance_report(self) -> pd.DataFrame:
        """
        Формирует итоговый балансовый отчёт с рыночной стоимостью и долями.

        Этапы:
        1. Объединение всех отчётов из `report_registry.report_list`.
        2. Добавление процентов распределения позиций из `distribution_table.distribution_table`.
        3. Группировка по `'ticker'`: сумма количества, остальное — `first`.
        4. Получение текущей цены через `moex.get_last_price()`.
        5. Расчёт: `Стоимость = Цена × Кол-во`, `% = Стоимость / ΣСтоимость`.

        :returns: DataFrame с колонками:
                  `'ticker'`, `'name'`, `'Кол-во (шт)'`, `'Размер лота'`,
                  `'Цена'`, `'Стоимость'`, `'%'`.
        :rtype: pd.DataFrame

        :raises ValueError: 
            - При пустом `report_registry.report_list` + пустом `distribution_table`,
            - При ошибке агрегации (например, нечисловые `'Кол-во (шт)'`).
        :raises KeyError: Если отсутствуют обязательные колонки (`'ticker'`, `'Кол-во (шт)'` и др.).
        :raises ConnectionError / HTTPError: При недоступности MOEX API в `get_last_price`.
        :raises RuntimeError: Если `moex.get_last_price()` возвращает `None` или некорректное значение.
        """
        balance_report_from_broker = pd.concat(
            self.report_registry.report_list, 
            ignore_index=True
            )
        balance_report = pd.concat(
            [balance_report_from_broker, self.dt.distribution_table], 
            ignore_index=True
            )
        balance_report = balance_report.groupby('ticker', as_index=False).agg(
            {
            'name': 'first',
            'Кол-во (шт)': 'sum',
            'Размер лота': 'first',
            'category': 'first'
            }
        ) 
        balance_report['Цена'] = balance_report.apply(self.get_price, axis = 1)
        balance_report['Стоимость'] = (
            balance_report['Цена']
            *balance_report['Кол-во (шт)']
            )
        balance_report['%'] = round(
            balance_report['Стоимость']/balance_report['Стоимость']
            .sum()*100, 2)
        self.balance_report = balance_report
        return balance_report
    
    @staticmethod
    def get_price(row):
        """Получает последнюю рыночную цену инструмента с MOEX через API.

        :param row: Строка DataFrame с колонкой `'ticker'`.
        :type row: pd.Series

        :returns: Цена в рублях (float).
        :rtype: float

        :raises KeyError: Если `'ticker'` отсутствует в `row`.
        :raises RuntimeError: 
            - Если `moex.get_last_price()` вернул `None`,
            - Если цена ≤ 0.
        :raises ConnectionError / HTTPError: При проблемах с сетью или API MOEX.
        """
        ticker = row['ticker']
        price = moex.get_last_price(ticker=ticker)
        return price