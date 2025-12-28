import pandas as pd
from .distribution_table import DistributionTable
from .balance_report import BalanceReport
import numpy as np
from typing import Optional


class TargetAllocator:
    """
    Аллокатор: рассчитывает, сколько и каких инструментов купить/продать для достижения целевого распределения.

    Принимает:
    - текущий портфель (`BalanceReport`),
    - целевое распределение (`DistributionTable`),
    - дополнительный депозит (`deposit`),
    - флаг разрешения продаж (`allow_sell`),
    - список тикеров, которые *можно* продавать (`tickers_to_sell`).

    Основные этапы:
    1. Оценка общей стоимости портфеля + депозит.
    2. Расчёт целевой стоимости по каждой позиции.
    3. Сравнение с текущей стоимостью → `delt (руб)`.
    4. Ограничение продаж (если `allow_sell=False` или фильтр по `tickers_to_sell`).
    5. Перевод в лоты (с учётом направления: `floor` для покупок, `ceil` для продаж).
    6. Корректировка под доступный бюджет с жадным алгоритмом (сначала дешёвые лоты).
    
    Атрибуты:
        br: Текущий балансовый отчёт.
        dt: Целевое распределение.
        money_count: Общая рыночная стоимость текущего портфеля (без депозита).
        AllocationTable: Итоговая таблица операций (заполняется в `get_distrib_of_money_df`).
        work_log: Строка с диагностикой расчётов (для отладки/логгера).
        deposit: Дополнительные средства для инвестирования.
        allow_sell: Разрешена ли продажа активов (кроме `tickers_to_sell`).
        tickers_to_sell: Список тикеров, которые *можно* продавать, даже если `allow_sell=False`.
    """

    def __init__(
            self,
            balance_report: BalanceReport ,
            distribution_table: DistributionTable,
            deposit:float = 0,
            allow_sell:bool = False,
            tickers_to_sell:list[str] | None = None
            ):
        """
        Инициализирует аллокатор.

        :param balance_report: Текущий портфель с рыночными ценами.
        :param distribution_table: Целевое распределение (уже обработанное).
        :param deposit: Дополнительные средства для инвестирования (по умолчанию 0).
        :param allow_sell: Разрешить ли продажу активов для ребалансировки.
        :param tickers_to_sell: Список тикеров, которые *можно* продавать
                                даже при `allow_sell=False` (например, для выхода из позиций).
        """
        self.br: BalanceReport = balance_report
        self.dt: DistributionTable = distribution_table
        self.money_count:Optional[float] = None 
        self.AllocationTable: pd.DataFrame
        self.work_log:str = ''
        self.deposit:float = deposit
        self.allow_sell:bool = allow_sell
        self.tickers_to_sell:list[str] = tickers_to_sell
        
    def get_money_count(self):
        """
        Вычисляет текущую рыночную стоимость портфеля (без депозита).

        :returns: Сумма колонки `'Стоимость'` в `self.br.balance_report`.
        :rtype: float

        :raises KeyError: Если отсутствует колонка `'Стоимость'`.
        :raises TypeError: Если значения в `'Стоимость'` не числовые.
        """
        money_count = self.br.balance_report['Стоимость'].sum()
        self.money_count = money_count
        return money_count

    def get_distrib_of_money_df(self) -> pd.DataFrame:
        """
        Рассчитывает таблицу операций для достижения целевого распределения.

        :returns: DataFrame с колонками:
            - исходные (`ticker`, `name`, `Размер лота`, `Цена`, `Стоимость_source`),
            - целевые (`Стоимость_target`, `%`),
            - дельты (`delt (руб)`, `delt (лот)`, `delt расчет`),
            - расчётные с учётом бюджета (`delt (лот)_calc`, `delt расчет_calc`, `Стоимость_calc`, `%_calc`).
        :rtype: pd.DataFrame

        :raises ValueError: 
            - При пустом `balance_report` или `distribution_table`,
            - При несогласованных тикерах/лотах (например, разный `Размер лота` для одного `ticker`).
        :raises KeyError: При отсутствии обязательных колонок в входных данных.
        :raises ZeroDivisionError: Если `Цена` или `Размер лота` = 0 у какого-либо инструмента.
        """
        money_count = self.get_money_count() + self.deposit
        df = self.dt.distribution_table.copy()
        df['Стоимость'] = (money_count*df['%']/100)
        df['Стоимость'] = df['Стоимость'].astype(float).round(1)
        merged_df = pd.merge(
            df, 
            self.br.balance_report, 
            on=['ticker', 'name', 'Размер лота'],
            suffixes=('_target', '_source'),
            how='outer'
            ).fillna(0)
        merged_df['delt (руб)'] = merged_df['Стоимость_target'] - merged_df['Стоимость_source']
        
        # Применение политики продаж
        if not self.allow_sell:
            merged_df['delt (руб)'] = (
                merged_df['delt (руб)'].apply(lambda x: max(x, 0))
                )
        else:
            if self.tickers_to_sell:
                mask = (
                    (merged_df['delt (руб)'] < 0) 
                    & (~merged_df['ticker'].isin(self.tickers_to_sell))
                )
                merged_df.loc[mask, 'delt (руб)'] = 0

        # Перевод в лоты: продажи — ceil (чтобы не оставить "хвост"), покупки — floor
        merged_df['delt (лот)'] = (
            merged_df['delt (руб)']/merged_df['Цена']/merged_df['Размер лота']
            )
        merged_df['delt (лот)'] = (
            merged_df['delt (лот)']
            .apply(lambda x: np.ceil(x) if x < 0 else np.floor(x))
            )
        
        # Расчёт стоимости дельты в рублях
        merged_df['delt расчет'] = (
            merged_df['delt (лот)']
            *merged_df['Размер лота']
            *merged_df['Цена']
            )
        
        # Корректировка под бюджет
        merged_df = self._adjust_for_funds(deposit=self.deposit, df=merged_df)

        # Итоговые расчётные значения
        merged_df['Стоимость_calc'] = merged_df['Стоимость_source'] + merged_df['delt расчет_calc']
        merged_df['%_calc'] = round(merged_df['Стоимость_calc']/merged_df['Стоимость_calc'].sum()*100, 2)
        
        self.AllocationTable = merged_df
        return self.AllocationTable

    def _adjust_for_funds(self, deposit: float, df: pd.DataFrame):
        """
        Корректирует объёмы покупок под доступный бюджет (продажи + депозит).

        Применяет жадный алгоритм: сначала дешёвые лоты → максимизируем кол-во операций.

        :param deposit: Дополнительные средства.
        :param df: Промежуточный DataFrame с колонками `delt расчет`, `Цена`, `Размер лота` и др.
        :returns: DataFrame с новыми колонками: `'delt (лот)_calc'`, `'delt расчет_calc'`.
        :rtype: pd.DataFrame

        .. note::
            - Продажи учитываются как источник средств (`sell_needed`).
            - Покупки ограничиваются доступным бюджетом.
            - Инструменты без покупок (`delt расчет ≤ 0`) не меняются.
        """
        sell_needed = abs(df[df['delt расчет'] < 0]['delt расчет'].sum())
        available_funds = sell_needed + deposit
        buy_orders = df[df['delt расчет'] > 0].copy()

        # Инициализация расчётных столбцов
        df['delt (лот)_calc'] = df['delt (лот)'].copy()
        df['delt расчет_calc'] = df['delt расчет'].copy()

        # Если нечего покупать, выходим
        if buy_orders.empty:
            self.work_log += f"\nНет покупок. Доступно: {available_funds}"
            return df

        # Считаем стоимость одного лота
        buy_orders['cost_per_lot'] = buy_orders['Цена'] * buy_orders['Размер лота']
        
        # Сортируем по возрастанию стоимости лота — сначала дешёвые
        buy_orders = buy_orders.sort_values('delt расчет')

        remaining_funds = available_funds
        total_spent = 0

        for idx in buy_orders.index:
            cost_per_lot = buy_orders.loc[idx, 'cost_per_lot']
            max_lots_by_target = int(buy_orders.loc[idx, 'delt (лот)'])  # целевое количество лотов

            # Сколько лотов можем реально купить
            affordable_lots = min(max_lots_by_target, int(remaining_funds // cost_per_lot))

            actual_cost = affordable_lots * cost_per_lot

            df.loc[idx, 'delt (лот)_calc'] = affordable_lots
            df.loc[idx, 'delt расчет_calc'] = actual_cost

            remaining_funds -= actual_cost
            total_spent += actual_cost

        # Обнуление покупок для инструментов, не вошедших в buy_orders (защита)
        for idx in df[~df.index.isin(buy_orders.index)].index:
            if df.loc[idx, 'delt расчет'] > 0:
                df.loc[idx, 'delt (лот)_calc'] = 0
                df.loc[idx, 'delt расчет_calc'] = 0

        self.work_log += f"\nБюджет на покупки: {available_funds:.0f}, потрачено: {total_spent:.0f}, остаток: {remaining_funds:.0f}"
        self.work_log += f'\nИтоговая дельта: {df["delt расчет_calc"].sum():.0f}'

        return df