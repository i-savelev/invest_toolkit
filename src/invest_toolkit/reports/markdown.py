from invest_toolkit.utils import log

import pandas as pd
from pathlib import Path
import datetime



def _load_template() -> str:
    """
    Загружает содержимое шаблона из файла.

    :param path: Путь к файлу шаблона.
    :type path: str
    :returns: Содержимое шаблона как строка.
    :rtype: str
    :raises FileNotFoundError: Если файл не существует.
    :raises ValueError: Если файл пуст после strip().
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
    target_stock = adjust_df[adjust_df['type']=='stock']['%_tgt'].sum()
    target_bonds = adjust_df[adjust_df['type']=='etf']['%_tgt'].sum()
    log.info(f'Общее количество денег: {all_money_sum}')
    log.info(f'Сумма в акциях: {bonds_sum}')
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

    
def _distrib_of_money_table(df:pd.DataFrame):
    """
    Формирует таблицу операций для вставки в отчёт.

    Включает:
    - тикер,
    - строку операции (`buy 10 шт. (...)`),
    - текущая, целевая и итоговая доли (%).

    :returns: DataFrame с колонками:
                `'ticker'`, `'buy/sell'`, `'%_src'`, `'%_tgt'`, `'%_res'`.
    :rtype: pd.DataFrame

    :raises KeyError: Если отсутствуют колонки `'d_lot_adjust'`, `'d_rub_adjust'` и др.
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

def _all_money_sum(df:pd.DataFrame):
    """
    Возвращает общую стоимость текущего портфеля (без депозита и плановых изменений).

    :returns: Сумма `'value_src'`.
    :rtype: float
    """
    return df['value_src'].sum()

def _stock_sum(df:pd.DataFrame):
    """
    Сумма стоимости позиций в категории `'stock'`.

    :returns: Сумма `'value_src'` для `type == 'stock'`.
    :rtype: float
    :raises KeyError: Если отсутствует колонка `'type'`.
    """
    df = df[df['type'] == 'stock']
    return df['value_src'].sum()

def _bonds_sum(df:pd.DataFrame):
    """
    Сумма стоимости позиций в категории `'bonds'`.

    :returns: Сумма `'value_src'` для `type == 'bonds'`.
    :rtype: float
    :raises KeyError: Если отсутствует колонка `'type'`.
    """
    df = df[df['type'] == 'etf']
    return df['value_src'].sum()


def _sell_buy_string(row):
    """
    Формирует читаемую строку операции: покупка/продажа + лоты + сумма.

    :param row: Строка DataFrame с колонками `'lot number'`, `'d_rub_adjust'`.
    :type row: pd.Series
    :returns: Строка вида `"buy 10 шт. (5000 руб.)"` или `"-"`.
    :rtype: str
    :raises KeyError: Если отсутствуют ожидаемые колонки.
    """
    if row['lot number'] > 0:
        return f'buy {round(row['lot number'])} шт. ({round(row['d_rub_adjust'])} руб.)'
    elif row['lot number'] < 0:
        return f'sell {abs(round(row['lot number']))} шт. ({round(row['d_rub_adjust'])} руб.)'
    else: return '-'

def _distrib_of_money_string(df:pd.DataFrame):
    """
    Формирует краткий текстовый список операций (для компактного отображения).

    :param df: DataFrame с колонкой `'buy/sell'`.
    :type df: pd.DataFrame
    :returns: Многострочная строка вида:
                "SBER: buy 10 шт. (5000 руб.)\\nGAZP: sell 5 шт. (2500 руб.)"
    :rtype: str
    """
    df = df[df['buy/sell'] != '-']
    string = ''
    for idx in df.index:
        string += f'{df.loc[idx, 'ticker']}: {df.loc[idx, 'buy/sell']}\n'
    return string

def _save_report(folder:str, report:str):
    """
    
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