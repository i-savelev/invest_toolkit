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
        df_target = self.dt.distribution_table.copy().sort_values('ticker')

        df_target = self.group_by_value(
           df=df_target,
            group_col='category',
            group_value='bonds',
            group_dict={
                'category': 'first',
                'ticker': ', '.join, 
                'name': ', '.join,
                'Размер лота': 'first',
                '%':'sum'
                }
        )
        df_target['Стоимость'] = (money_count*df_target['%']/100)
        df_target['Стоимость'] = df_target['Стоимость'].astype(float).round(1)

        df_source = self.br.balance_report.copy().sort_values('ticker')

        df_source = self.group_by_value(
            df=df_source,
            group_col='category',
            group_value='bonds',
            group_dict={
                'category': 'first',
                'ticker': ', '.join, 
                'name': ', '.join,
                'Кол-во (шт)': 'first',
                'Размер лота': 'first',
                'Цена': 'first',
                'Стоимость': 'sum',
                '%':'sum'
                }
        )

        merged_df = pd.merge(
            df_target, 
            df_source, 
            on=['ticker', 'name', 'Размер лота', 'category'],
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
        merged_df = self._adjust_for_funds3(deposit=self.deposit, df=merged_df)

        # Итоговые расчётные значения
        merged_df['Стоимость_calc'] = merged_df['Стоимость_source'] + merged_df['delt расчет_calc']
        merged_df['%_calc'] = round(merged_df['Стоимость_calc']/merged_df['Стоимость_calc'].sum()*100, 2)
        
        self.AllocationTable = merged_df
        return self.AllocationTable

    @staticmethod
    def group_by_value(
            df: pd.DataFrame,
            group_col: str,
            group_value: str,
            group_dict: dict
        ) -> pd.DataFrame:
        """
        Группирует строки, где `group_col == group_value`, в одну строку.
        
        - Числовые столбцы: суммируются.
        - Текстовые столбцы: заменяются на значения из `new_row_values`.
        
        :param df: Исходный DataFrame
        :param group_col: Имя столбца для группировки (например, 'category')
        :param group_value: Значение, которое нужно агрегировать (например, 'bonds')
        :param new_row_values: Словарь с новыми значениями для нечисловых колонок
        :return: Новый DataFrame с агрегированной строкой
        """
        # Проверка наличия столбца
        if group_col not in df.columns:
            raise KeyError(f"Столбец '{group_col}' не найден в DataFrame")

        # Разделяем строки
        mask = df[group_col] == group_value
        df_group = df[mask].copy()
        df_others = df[~mask].copy()

        # Если нет строк для группировки — возвращаем как есть
        if df_group.empty:
            return df_others.copy()

        grouped = df_group.groupby(['category'], as_index=False).agg(group_dict
                
            )
        df_final = pd.concat([df_others, grouped], ignore_index=True)
        
        return df_final


    def _adjust_for_funds1(self, deposit: float, df: pd.DataFrame):
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
    
    def _adjust_for_funds2(self, deposit: float, df: pd.DataFrame):
        """
        Корректирует объёмы покупок, распределяя средства пропорционально целевым дельтам.

        Вместо жадного алгоритма (сначала дешёвые лоты), все покупки масштабируются
        пропорционально их доле в общей потребности.

        :param deposit: Дополнительные средства.
        :param df: Промежуточный DataFrame с колонками `delt расчет`, `Цена`, `Размер лота` и др.
        :returns: DataFrame с новыми колонками: `'delt (лот)_calc'`, `'delt расчет_calc'`.
        :rtype: pd.DataFrame
        """
        sell_needed = abs(df[df['delt расчет'] < 0]['delt расчет'].sum())
        available_funds = sell_needed + deposit
        buy_orders = df[df['delt расчет'] > 0].copy()

        # Инициализация расчётных столбцов
        df['delt (лот)_calc'] = 0.0
        df['delt расчет_calc'] = 0.0

        if buy_orders.empty:
            self.work_log += f"\nНет покупок. Доступно: {available_funds}"
            return df

        total_target_buy = buy_orders['delt расчет'].sum()  # Суммарная цель по покупкам (руб)

        if available_funds >= total_target_buy:
            # Хватает средств — выделяем всё
            df.loc[buy_orders.index, 'delt (лот)_calc'] = df.loc[buy_orders.index, 'delt (лот)']
            df.loc[buy_orders.index, 'delt расчет_calc'] = df.loc[buy_orders.index, 'delt расчет']
        else:
            # Недостаточно средств — пропорционально уменьшаем
            scale_factor = available_funds / total_target_buy
            df.loc[buy_orders.index, 'delt расчет_calc'] = (buy_orders['delt расчет'] * scale_factor)

            # Округляем вниз до полных лотов
            for idx in buy_orders.index:
                target_cost = df.loc[idx, 'delt расчет_calc']
                cost_per_lot = df.loc[idx, 'Цена'] * df.loc[idx, 'Размер лота']

                if cost_per_lot <= 0:
                    continue

                # Максимум лотов, которые можем себе позволить после масштабирования
                lots = int(target_cost // cost_per_lot)
                df.loc[idx, 'delt (лот)_calc'] = lots
                df.loc[idx, 'delt расчет_calc'] = lots * cost_per_lot

        # Обновляем итоговую потраченную сумму
        total_spent = df['delt расчет_calc'].sum()
        remaining_funds = available_funds - total_spent

        self.work_log += f"\nБюджет на покупки: {available_funds:.0f}, потрачено: {total_spent:.0f}, остаток: {remaining_funds:.0f}"
        self.work_log += f'\nИтоговая дельта: {total_spent:.0f}'

        return df

    def _adjust_for_funds3(self, deposit: float, df: pd.DataFrame):
        """
        Распределяет средства пропорционально целям, затем использует остатки для докупки лотов.

        Этапы:
        1. Пропорциональное масштабирование целевых покупок.
        2. Округление до целых лотов (вниз).
        3. Повторная закупка за остатки — по одному лоту, пока хватает средств.
        Покупка идёт тем, кто больше всего "отстаёт" от цели (по относительной недостаче).
        """
        sell_needed = abs(df[df['delt расчет'] < 0]['delt расчет'].sum())
        available_funds = sell_needed + deposit
        buy_orders = df[df['delt расчет'] > 0].copy()

        df['delt (лот)_calc'] = 0.0
        df['delt расчет_calc'] = 0.0

        if buy_orders.empty:
            self.work_log += f"\nНет покупок. Доступно: {available_funds}"
            return df

        total_target_buy = buy_orders['delt расчет'].sum()

        # === Этап 1: Пропорциональное распределение ===
        if available_funds >= total_target_buy:
            # Хватает средств — покупаем всё
            df.loc[buy_orders.index, 'delt (лот)_calc'] = df.loc[buy_orders.index, 'delt (лот)']
            df.loc[buy_orders.index, 'delt расчет_calc'] = df.loc[buy_orders.index, 'delt расчет']
        else:
            # Масштабируем пропорционально
            scale_factor = available_funds / total_target_buy
            for idx in buy_orders.index:
                target_cost = buy_orders.loc[idx, 'delt расчет'] * scale_factor
                cost_per_lot = df.loc[idx, 'Цена'] * df.loc[idx, 'Размер лота']

                if cost_per_lot <= 0:
                    continue

                lots = int(target_cost // cost_per_lot)
                df.loc[idx, 'delt (лот)_calc'] = lots
                df.loc[idx, 'delt расчет_calc'] = lots * cost_per_lot

        # === Этап 2: Распределение остатков ===
        total_spent = df['delt расчет_calc'].sum()
        remaining_funds = available_funds - total_spent

        # Собираем список кандидатов для докупки
        residual_candidates = []

        for idx in buy_orders.index:
            current_cost = df.loc[idx, 'delt расчет_calc']
            target_cost = df.loc[idx, 'delt расчет']
            cost_per_lot = df.loc[idx, 'Цена'] * df.loc[idx, 'Размер лота']

            if cost_per_lot <= 0 or target_cost <= current_cost + 1e-3:
                continue  # уже достигли цели или некорректная цена

            # Сколько ещё хотим (в рублях)
            remaining_needed = target_cost - current_cost
            # Сколько лотов можно докупить (минимум — один, максимум — ограничено средствами)
            if remaining_needed >= cost_per_lot and remaining_funds >= cost_per_lot:
                # Относительное отклонение: насколько далеко от цели
                relative_shortfall = remaining_needed / target_cost
                residual_candidates.append({
                    'idx': idx,
                    'cost_per_lot': cost_per_lot,
                    'relative_shortfall': relative_shortfall,
                })

        # Сортируем по убыванию относительного отклонения — сначала те, кто больше всего "отстаёт"
        residual_candidates.sort(key=lambda x: x['relative_shortfall'], reverse=True)

        # === Этап 3: Покупаем по одному лоту, пока хватает средств ===
        improved_spent = 0

        for candidate in residual_candidates:
            idx = candidate['idx']
            cost = candidate['cost_per_lot']

            if remaining_funds >= cost:
                df.loc[idx, 'delt (лот)_calc'] += 1
                df.loc[idx, 'delt расчет_calc'] += cost
                remaining_funds -= cost
                improved_spent += cost

        total_spent += improved_spent

        self.work_log += f"\nБюджет на покупки: {available_funds:.0f}"
        self.work_log += f", израсходовано: {total_spent:.0f}"
        self.work_log += f", остаток: {remaining_funds:.0f}"
        self.work_log += f'\nИтоговая дельта: {total_spent:.0f}'

        return df
