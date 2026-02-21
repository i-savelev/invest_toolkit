import pandas as pd
from typing import List
from invest_toolkit.utils import log
import numpy as np
from invest_toolkit.utils import log_dataframe

@log_dataframe
def allocation_report(report_df:pd.DataFrame, allocation_df:pd.DataFrame, deposit:float)->pd.DataFrame:
    log.info('Объединение с таблицей целевых распределений...')
    money_count = report_df['value'].sum()+deposit
    allocation_df['value'] = (money_count*allocation_df['%']/100).round(2)
    merged_df = pd.merge(
        report_df, 
        allocation_df, 
        on=['ticker'],
        suffixes=('_src', '_tgt'),
        how='outer'
        ).fillna(0)
    merged_df['d_rub'] = (
        merged_df['value_tgt'] - merged_df['value_src']
        )
    merged_df = merged_df[merged_df.columns.drop(
        ['isin', 'name', 'cap']
        )]
    
    merged_df['d_lot'] = (
        merged_df['d_rub']/merged_df['price']/merged_df['lot_size']
        )
    merged_df['d_lot'] = (
        merged_df['d_lot']
        .apply(lambda x: np.ceil(x) if x < 0 else np.floor(x))
        )
    
    # Расчёт стоимости дельты в рублях
    merged_df['d_rub_calc'] = (
        merged_df['d_lot']
        *merged_df['lot_size']
        *merged_df['price']
        )
    
    return merged_df

@log_dataframe
def group_by_category(
        df: pd.DataFrame,
        group_col: str,
        tickers_list: List[str],
        )->pd.DataFrame:
    log.info('Группировка по категориям...')
    # Проверка наличия столбца
    if group_col not in df.columns:
        raise KeyError(f"Столбец '{group_col}' не найден в DataFrame")

    # Разделяем строки
    mask = df[group_col].isin(tickers_list)
    df_group = df[mask].copy()
    df_others = df[~mask].copy()

    # Если нет строк для группировки — возвращаем как есть
    if df_group.empty:
        return df_others.copy()

    grouped = df_group.groupby(['type'], as_index=False).agg(
            {
            'type': 'first',
            'ticker': ', '.join, 
            'count_pieces': 'first',
            'lot_size': 'first',
            'price': 'first',
            'value_src': 'sum',
            'value_tgt': 'sum',
            '%_tgt':'sum',
            '%_src':'sum',
            'd_rub': 'sum',
            'd_lot': 'sum',
            'd_rub_calc': 'sum',
            }
        )
    df_final = pd.concat([df_others, grouped], ignore_index=True)
    
    return df_final

@log_dataframe
def allow_sell(df:pd.DataFrame, allow_sell:bool, tickers_to_sell:List[str])->pd.DataFrame:
    # Применение политики продаж
    log.info('Применение политики продаж...')
    if not allow_sell:
        df['d_rub_calc'] = (
            df['d_rub_calc'].apply(lambda x: max(x, 0))
            )
    else:
        if tickers_to_sell:
            mask = (
                (df['d_rub'] < 0) 
                & (~df['ticker'].isin(tickers_to_sell))
            )
            df.loc[mask, 'd_rub_calc'] = 0
    return df

@log_dataframe
def adjust_for_deposit(deposit: float, df: pd.DataFrame)->pd.DataFrame:
    """
    Распределяет средства пропорционально целям, затем использует остатки для докупки лотов.

    Этапы:
    1. Пропорциональное масштабирование целевых покупок.
    2. Округление до целых лотов (вниз).
    3. Повторная закупка за остатки — по одному лоту, пока хватает средств.
    Покупка идёт тем, кто больше всего "отстаёт" от цели (по относительной недостаче).
    """
    log.info('Корректировка распределения под депозит...')
    sell_needed = abs(df[df['d_rub_calc'] < 0]['d_rub_calc'].sum())
    available_funds = sell_needed + deposit
    buy_orders = df[df['d_rub_calc'] > 0].copy()

    df['d_lot_adjust'] = 0.0
    df['d_rub_adjust'] = 0.0

    if buy_orders.empty:
        log.info(f"\nНет покупок. Доступно: {available_funds}")
        return df

    total_target_buy = buy_orders['d_rub_calc'].sum()

    # === Этап 1: Пропорциональное распределение ===
    if available_funds >= total_target_buy:
        # Хватает средств — покупаем всё
        df.loc[buy_orders.index, 'd_lot_adjust'] = df.loc[buy_orders.index, 'd_lot']
        df.loc[buy_orders.index, 'd_rub_adjust'] = df.loc[buy_orders.index, 'd_rub_calc']
    else:
        # Масштабируем пропорционально
        scale_factor = available_funds / total_target_buy
        for idx in buy_orders.index:
            target_cost = buy_orders.loc[idx, 'd_rub_calc'] * scale_factor
            cost_per_lot = df.loc[idx, 'price'] * df.loc[idx, 'lot_size']

            if cost_per_lot <= 0:
                continue

            lots = int(target_cost // cost_per_lot)
            df.loc[idx, 'd_lot_adjust'] = lots
            df.loc[idx, 'd_rub_adjust'] = lots * cost_per_lot

    # === Этап 2: Распределение остатков ===
    total_spent = df['d_rub_adjust'].sum()
    remaining_funds = available_funds - total_spent

    # Собираем список кандидатов для докупки
    residual_candidates = []

    for idx in buy_orders.index:
        current_cost = df.loc[idx, 'd_rub_adjust']
        target_cost = df.loc[idx, 'd_rub_calc']
        cost_per_lot = df.loc[idx, 'price'] * df.loc[idx, 'lot_size']

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
            df.loc[idx, 'd_lot_adjust'] += 1
            df.loc[idx, 'd_rub_adjust'] += cost
            remaining_funds -= cost
            improved_spent += cost

    # === Этап 4: Применяем продажи (если они были разрешены) ===
    # Продажи не требуют бюджета — они его создают, поэтому применяем их "как есть"
    sell_mask = df['d_rub_calc'] < 0
    df.loc[sell_mask, 'd_lot_adjust'] = df.loc[sell_mask, 'd_lot']
    df.loc[sell_mask, 'd_rub_adjust'] = df.loc[sell_mask, 'd_rub_calc']
    total_spent += improved_spent
    df['value_res'] = df['value_src'] + df['d_rub_adjust']
    df['%_res'] = round(df['value_res']/df['value_res'].sum()*100, 2)
    

    log.info(f"Бюджет на покупки: {available_funds:.0f}")
    log.info(f"израсходовано: {total_spent:.0f}")
    log.info(f"остаток: {remaining_funds:.0f}")
    log.info(f'Итоговая дельта: {total_spent:.0f}')

    return df
