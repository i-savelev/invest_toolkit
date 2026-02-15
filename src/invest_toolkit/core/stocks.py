import pandas as pd
from invest_toolkit.utils import log, log_dataframe

@log_dataframe
def get_stock_info(
        moex_api_df:pd.DataFrame = None,
        sl_stock_df:pd.DataFrame = None,
        ir_df:pd.DataFrame = None,
        free_float_df:pd.DataFrame = None,
    )->pd.DataFrame:
    df_list = []
    _moex_api_df:pd.DataFrame = moex_api_df[moex_api_df['type']=='stock']
    _moex_api_d_long = _moex_api_df.melt(
        id_vars=['ticker'],          # Столбец(-ы), которые остаются как есть
        var_name='indicator',        # Имя нового столбца для названий исходных колонок
        value_name='value'           # Имя нового столбца для значений
        )
    if moex_api_df is not None: df_list.append(_moex_api_d_long)
    if sl_stock_df is not None: df_list.append(sl_stock_df)
    if ir_df is not None: df_list.append(ir_df)
    if free_float_df is not None: df_list.append(free_float_df)
    df = pd.concat(df_list)
    return df
