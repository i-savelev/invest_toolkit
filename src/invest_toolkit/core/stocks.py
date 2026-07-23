import pandas as pd
from invest_toolkit.utils import log, log_dataframe

@log_dataframe
def get_stock_info(
    moex_api_df: pd.DataFrame | None = None,
    sl_stock_df: pd.DataFrame | None = None,
    ir_df: pd.DataFrame | None = None,
    free_float_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Объединяет данные из различных источников в единый длинный формат.

    :param moex_api_df: Данные с MOEX API (получается через `io.moex.all_instruments_info`).
    :param sl_stock_df: Финансовые показатели со SmartLab (получается через `io.stocks.merge_csv_files`).
    :param ir_df: Рейтинг IR (получается через `io.stocks.ir_rating`).
    :param free_float_df: Данные Free Float (получается через `io.stocks.free_float`).
    :returns: DataFrame в длинном формате (ticker, indicator, value, type).
    """
    df_list = []

    if moex_api_df is not None and not moex_api_df.empty:
        _moex_api_df = moex_api_df[moex_api_df['cap'] > 0]
        # Дополнительно: пропустить, если после фильтрации стало пусто
        if not _moex_api_df.empty:
            _moex_api_d_long = _moex_api_df.melt(
                id_vars=['ticker'],
                var_name='indicator',
                value_name='value'
            )
            _moex_api_d_long['type'] = 'moex'
            df_list.append(_moex_api_d_long)

    if sl_stock_df is not None and not sl_stock_df.empty:
        sl_stock_df = sl_stock_df.copy()
        sl_stock_df['type'] = 'smartlab'
        df_list.append(sl_stock_df)

    if ir_df is not None and not ir_df.empty:
        ir_df = ir_df.copy()
        ir_df['type'] = 'smartlab'
        df_list.append(ir_df)

    if free_float_df is not None and not free_float_df.empty:
        free_float_df = free_float_df.copy()
        free_float_df['type'] = 'moex'
        df_list.append(free_float_df)

    if not df_list:
        return pd.DataFrame(columns=['ticker', 'indicator', 'value', 'type'])

    df_list = [df for df in df_list if not df.empty]

    if not df_list:
        return pd.DataFrame(columns=['ticker', 'indicator', 'value', 'type'])

    df = pd.concat(df_list, ignore_index=True)
    return df


def _metric_to_series(ticker:str, metric:str, df:pd.DataFrame, n:int) -> pd.Series:
    """
    Извлекает последние N значений метрики для тикера.

    :param ticker: Тикер инструмента.
    :param metric: Название показателя.
    :param df: DataFrame с финансовыми данными (получается через `get_stock_info`).
    :param n: Количество последних лет для анализа.
    :returns: Series со значениями метрики по годам.
    """
    n = n+1
    last_n:pd.Series = pd.Series()
    if metric in df['indicator'].unique().tolist():
        _df = df[(df['indicator']==metric) & (df['ticker']==ticker)].set_index('year')
        s = _df['value']
        s_clean = pd.to_numeric(s, errors='coerce').fillna(0)
        last_n = s_clean.iloc[-n:]
        if len(last_n) < n:
            missing = n - len(last_n)
            padding = pd.Series([0.0] * missing)
            if not padding.empty and not last_n.empty:
                last_n = pd.concat([padding, last_n]).iloc[-n:]
    return last_n


def grow_score(ticker:str, metric:str, df:pd.DataFrame, n:int)->tuple:
    """
    Рассчитывает показатель роста метрики за последние N лет.

    :param ticker: Тикер инструмента.
    :param metric: Название показателя (например, 'Чистая прибыль, млрд руб').
    :param df: DataFrame с финансовыми данными (получается через `get_stock_info`).
    :param n: Количество лет для анализа.
    :returns: Кортеж (оценка от 0 до 1, строка с описанием расчета).
    """
    s = _metric_to_series(ticker, metric, df, n)
    if s is None:
        calc = f'Рост [{metric}]: 0'
        return None, calc
    l = s.values.tolist()
    l.reverse()
    score = 0
    val = 0
    for i, value in enumerate(l):
        if i >= len(l)-1: break
        if (value >= l[i+1]) and (value > 0):
            val += 1
        if (value < 0):
            val -= 1
    score = round(val/n, 2)
    calc = f'Рост [{metric}]: {val}/{n} = {score}'
    res = score, calc
    return  res

def count_score(ticker:str, metric:str, df:pd.DataFrame, n:int)->tuple:
    """
    Рассчитывает оценку частоты положительного значения метрики.

    :param ticker: Тикер инструмента.
    :param metric: Название показателя (например, 'Див.выплата, млрд руб').
    :param df: DataFrame с финансовыми данными (получается через `get_stock_info`).
    :param n: Количество лет для анализа.
    :returns: Кортеж (оценка от 0 до 1, строка с описанием расчета).
    """
    s = _metric_to_series(ticker, metric, df, n)
    if s is None:
        calc = f'Кол-во [{metric}]: 0'
        return None, calc
    l = s.values.tolist()
    l.reverse()
    score = 0
    val = 0
    for i, value in enumerate(l):
        if i >= len(l)-1: break
        if value > 0:
            val += 1
    score = round(val/n, 2)
    calc = f'Кол-во [{metric}]: {val}/{n} = {score}'
    res = score, calc
    return res

def ir_score(ticker:str, df:pd.DataFrame):
    """
    Получает рейтинг IR для тикера.

    :param ticker: Тикер инструмента.
    :param df: DataFrame с рейтингами (получается через `get_stock_info` -> источник `io.stocks.ir_rating`).
    :returns: Значение рейтинга (0, если не найдено).
    """
    filtered_ir = df[(df['indicator'] == 'ir')]
    filtered_ir = filtered_ir.set_index('ticker')
    for _ticker in filtered_ir.index.to_list():
        if len(str(_ticker))>2:
            if _ticker in ticker:
                rating = filtered_ir.loc[_ticker]['value']
                return rating
        elif _ticker==ticker:
            rating = filtered_ir.loc[_ticker]['value']
            return rating
    return 0
