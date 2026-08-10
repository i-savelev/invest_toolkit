from invest_toolkit.utils import log

import pandas as pd
from pathlib import Path
import datetime
TRACKED_TICKERS = ('LQDT', 'SBMM')


def _money_market_mask(df: pd.DataFrame) -> pd.Series:
    """Возвращает маску строк денежного рынка по конфигурационной категории или типу.

    :param df: DataFrame с портфельными данными.
    :returns: Булева маска строк денежного рынка.
    """
    category_series = df['category'].astype(str).str.lower() if 'category' in df.columns else pd.Series('', index=df.index)
    type_series = df['type'].astype(str).str.lower() if 'type' in df.columns else pd.Series('', index=df.index)
    return (
        category_series.str.contains('bond|облиг|денеж|fund|etf', regex=True, na=False)
        | type_series.isin(['bond', 'etf'])
    )



def _load_template() -> str:
    """
    Загружает содержимое шаблона отчёта из файла.

    :returns: Строка с содержимым шаблона (templates/md_template.md).
    """
    TEMPLATE_DIR = Path(__file__).parent / "templates"
    template_path = TEMPLATE_DIR / 'md_template.md'
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден по пути: {template_path}")
    content = template_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError("Файл шаблона пуст.")
    return content

def generate(save_path: str, deposit:float, adjust_df:pd.DataFrame)->None:
    """
    Генерирует итоговый отчёт в формате Markdown.

    :param save_path: Директория для сохранения отчёта.
    :param deposit: Сумма депозита (для отображения в отчёте).
    :param adjust_df: DataFrame с планом операций (получается через `core.target_allocation.adjust_for_deposit`).
    """
    log.info('Генерация отчета в формат markdown...')
    distribution_table = _distrib_of_money_table(adjust_df)
    distribution_string = _distrib_of_money_string(df=distribution_table)
    all_money_sum = round(_all_money_sum(adjust_df))
    stock_sum = round(_stock_sum(adjust_df),0)
    bonds_sum = round(_bonds_sum(adjust_df),0)
    stock_percent = round(stock_sum/all_money_sum*100, 1)
    bonds_percent = round(bonds_sum/all_money_sum*100, 1)
    date = datetime.date.today()
    money_market_mask = _money_market_mask(adjust_df)
    target_bonds = round(adjust_df.loc[money_market_mask, '%_tgt'].sum(), 1)
    target_stock = round(adjust_df.loc[~money_market_mask, '%_tgt'].sum(), 1)
    tracked_rows = adjust_df[
        adjust_df['ticker'].isin(TRACKED_TICKERS)
        | adjust_df['ticker'].astype(str).str.contains('LQDT|SBMM', regex=True, na=False)
    ]
    if tracked_rows.empty:
        log.warning(f"Tracked tickers not found in markdown input: {list(TRACKED_TICKERS)}")
    else:
        log.info(
            "Tracked ticker rows in markdown input: "
            f"{tracked_rows[['ticker', 'type', 'value_src', 'value_tgt', 'd_lot_adjust', 'd_rub_adjust', '%_src', '%_tgt', '%_res']].to_dict(orient='records')}"
        )
    log.info(f'Общее количество денег: {all_money_sum}')
    log.info(f'Сумма в акциях: {stock_sum}')
    log.info(f'Сума в фондах: {bonds_sum}')
    log.info(f'Процент акций: {stock_percent}')
    log.info(f'Процент фондов: {bonds_percent}')
    context = {
        'all_money_sum':all_money_sum,
        'stock_sum':stock_sum,
        'stock_percent':stock_percent,
        'bonds_sum':bonds_sum,
        'bonds_percent':bonds_percent,
        "deposit": deposit,
        "distribution_table": distribution_table.to_markdown(index=False),
        "distribution_string": distribution_string,
        "date": date,
        'stock_target': target_stock, 
        'bonds_target': target_bonds,
    }

    try:
        report = _load_template().format_map(context)
        log.info(f'Текст отчета {date}\n{report}')
        _save_report(save_path, report)
    except KeyError as e:
        raise ValueError(f"В шаблоне отсутствует переменная: {e}")
    except Exception as e:
        raise ValueError(f"Ошибка при форматировании шаблона: {e}")

    
def _distrib_of_money_table(df:pd.DataFrame)-> pd.DataFrame:
    """
    Формирует таблицу операций для вставки в отчёт.

    :param df: DataFrame с планом операций (получается через `adjust_for_deposit`).
    :returns: DataFrame с колонками: ticker, buy/sell, %_src, %_tgt, %_res.
    """
    df = df[
            [
            'ticker', 
            'd_lot_adjust',
            'd_rub_adjust',
            '%_src',
            '%_tgt',
            '%_res'
            ]
        ]
    df = df.rename(columns={
            'd_lot_adjust':'lot number',
            }
        )
    
    df['buy/sell'] = df.apply(_sell_buy_string, axis = 1)
    df = df[
            [
            'ticker',
            'buy/sell',
            '%_src',
            '%_tgt',
            '%_res'
            ]
        ]
    return df

def _all_money_sum(df:pd.DataFrame)-> float:
    """Возвращает общую стоимость текущего портфеля.

    :param df: DataFrame с данными портфеля.
    :returns: Сумма столбца 'value_src'.
    """
    return df['value_src'].sum()

def _stock_sum(df:pd.DataFrame)-> float:
    """Сумма стоимости позиций в категории 'stock'.

    :param df: DataFrame с данными портфеля.
    :returns: Сумма стоимости акций.
    """
    df = df[~_money_market_mask(df)]
    return df['value_src'].sum()

def _bonds_sum(df:pd.DataFrame)-> float:
    """Сумма стоимости позиций в категории 'etf' (условно облигации/фонды).

    :param df: DataFrame с данными портфеля.
    :returns: Сумма стоимости фондов.
    """
    df = df[_money_market_mask(df)]
    return df['value_src'].sum()


def _sell_buy_string(row)->str:
    """Формирует читаемую строку операции.

    :param row: Строка DataFrame с данными операции.
    :returns: Строка вида "buy 10 шт. (5000 руб.)" или "-".
    """
    if row['lot number'] > 0:
        return f'buy {round(row['lot number'])} шт. ({round(row['d_rub_adjust'])} руб.)'
    elif row['lot number'] < 0:
        return f'sell {abs(round(row['lot number']))} шт. ({round(row['d_rub_adjust'])} руб.)'
    else: return '-'

def _distrib_of_money_string(df:pd.DataFrame)->str:
    """Формирует краткий текстовый список операций.

    :param df: DataFrame с таблицей операций.
    :returns: Многострочная строка со списком покупок/продаж.
    """
    df = df[df['buy/sell'] != '-']
    string = ''
    for idx in df.index:
        string += f'{df.loc[idx, 'ticker']}: {df.loc[idx, 'buy/sell']}\n'
    return string

def _save_report(folder:str, report:str):
    """Сохраняет текст отчёта в файл.

    :param folder: Директория для сохранения.
    :param report: Текст отчёта Markdown.
    """
    if not isinstance(folder, str):
        raise TypeError("Путь к файлу должен быть строкой.")

    if report is None:
        raise ValueError(
            "Отчет еще не был сгенерирован. Вызовите generate_report() перед save_report()."
        )
    date = datetime.date.today()
    file_path = Path(folder).joinpath(f'broker_report_{date}.md')
    try:
        # Создаем родительские директории, если их нет
        # file_path.parent.mkdir(parents=True, exist_ok=True)
        # # Записываем отчет в файл
        file_path.write_text(report, encoding="utf-8")
        log.info(f'отчет сохранен в файл {file_path}')
    except OSError as e:
        raise OSError(f"Не удалось сохранить отчет по пути '{file_path}': {e}") from e
