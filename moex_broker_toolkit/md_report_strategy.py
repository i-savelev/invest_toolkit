import pandas as pd
from .report_strategy import ReportStrategy
from .target_allocator import TargetAllocator
from pathlib import Path
import datetime

class MdReportStrategy(ReportStrategy):
    """
    Стратегия генерации отчёта в формате Markdown на основе шаблона.

    Использует `str.format_map()` для подстановки данных из `TargetAllocator` в шаблон.
    Ожидает, что шаблон содержит переменные, такие как:
    - `{all_money_sum}`, `{stock_sum}`, `{stock_percent}` и др.
    - `{distribution_table}` — Markdown-таблица (через `df.to_markdown`),
    - `{distribution_string}` — краткий список операций вида `"SBER: buy 10 шт. (5000 руб.)"`.

    .. note::
        Класс предполагает, что:
        - `TargetAllocator.get_distrib_of_money_df()` уже был вызван,
        - `DistributionTable.df_dict` содержит лист `'categories'` с категориями `'stock'` и `'bonds'`.

    Атрибуты:
        targetAllocator: Экземпляр аллокатора с расчётами.
        _template: Строка шаблона, загруженная из файла.
    """

    def __init__(
            self,
            targetAllocator: TargetAllocator,
            template_path:str
            ) -> None:
        """
        Инициализирует стратегию и загружает шаблон.

        :param targetAllocator: Экземпляр `TargetAllocator` с выполненными расчётами.
        :param template_path: Путь к файлу шаблона (например, `report.md.j2` или `report_template.md`).
        :raises FileNotFoundError: Если файл шаблона не найден.
        :raises ValueError: Если файл шаблона пуст.
        """
        self.targetAllocator = targetAllocator
        self._template = self._load_template(template_path)

    def _load_template(self, path: str) -> str:
        """
        Загружает содержимое шаблона из файла.

        :param path: Путь к файлу шаблона.
        :type path: str
        :returns: Содержимое шаблона как строка.
        :rtype: str
        :raises FileNotFoundError: Если файл не существует.
        :raises ValueError: Если файл пуст после strip().
        """
        template_path = Path(path)
        if not template_path.exists():
            raise FileNotFoundError(f"Шаблон не найден по пути: {template_path}")
        content = template_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError("Файл шаблона пуст.")
        return content

    def generate(self) -> str:
        """
        Генерирует итоговый Markdown-отчёт путём подстановки данных в шаблон.

        Извлекает:
        - итоговые суммы (`all_money_sum`, `stock_sum`, `bonds_sum`),
        - доли (`stock_percent`, `bonds_percent`),
        - целевые доли из `'categories'`,
        - таблицу и строку операций.

        :returns: Готовый отчёт в формате Markdown.
        :rtype: str

        :raises KeyError: 
            - Если в `AllocationTable` отсутствуют ожидаемые колонки,
            - Если в `df_dict['categories']` нет категории `'stock'` или `'bonds'`.
        :raises IndexError: Если категория `'stock'`/`'bonds'` найдена, но нет значения в `'%'`.
        :raises ValueError: 
            - При ошибке форматирования шаблона (отсутствует переменная),
            - Если шаблон некорректен.
        :raises AttributeError: Если `AllocationTable` не инициализирован.
        """
        deposit = self.targetAllocator.deposit
        distribution_table = self.distrib_of_money_table()
        distribution_string = self.distrib_of_money_string(distribution_table)
        all_money_sum = round(self.all_money_sum(),)
        stock_sum = round(self.stock_sum(),0)
        bonds_sum = round(self.bonds_sum(),0)
        stock_percent = round(stock_sum/all_money_sum*100, 1)
        bonds_percent = round(bonds_sum/all_money_sum*100, 1)
        date = datetime.date.today()
        target_stock = self.targetAllocator.dt.df_dict['categories'].loc[
            self.targetAllocator.dt.df_dict['categories']['category'] == 'stock', 
            '%'
            ].iloc[0]
        target_bonds = self.targetAllocator.dt.df_dict['categories'].loc[
            self.targetAllocator.dt.df_dict['categories']['category'] == 'bonds', 
            '%'
            ].iloc[0]
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
            return self._template.format_map(context)
        except KeyError as e:
            raise ValueError(f"В шаблоне отсутствует переменная: {e}")
        except Exception as e:
            raise ValueError(f"Ошибка при форматировании шаблона: {e}")

        
    def distrib_of_money_table(self):
        """
        Формирует таблицу операций для вставки в отчёт.

        Включает:
        - тикер,
        - строку операции (`buy 10 шт. (...)`),
        - текущая, целевая и итоговая доли (%).

        :returns: DataFrame с колонками:
                  `'ticker'`, `'buy/sell'`, `'%_source'`, `'%_target'`, `'%_calc'`.
        :rtype: pd.DataFrame

        :raises KeyError: Если отсутствуют колонки `'delt (лот)_calc'`, `'delt расчет_calc'` и др.
        """
        df = self.targetAllocator.AllocationTable[
                [
                'ticker', 
                'delt (лот)_calc',
                'delt расчет_calc',
                '%_source',
                '%_target',
                '%_calc'
                ]
            ]
        df = df.rename(columns={
                'delt (лот)_calc':'lot number',
                }
            )
        
        df['buy/sell'] = df.apply(self.sell_buy_string, axis = 1)
        df = df[
            [
                'ticker',
                'buy/sell',
                '%_source',
                '%_target',
                '%_calc'
                ]
            ]
        return df
    
    def all_money_sum(self):
        """
        Возвращает общую стоимость текущего портфеля (без депозита и плановых изменений).

        :returns: Сумма `'Стоимость_source'`.
        :rtype: float
        """
        return self.targetAllocator.AllocationTable['Стоимость_source'].sum()
    
    def stock_sum(self):
        """
        Сумма стоимости позиций в категории `'stock'`.

        :returns: Сумма `'Стоимость_source'` для `category == 'stock'`.
        :rtype: float
        :raises KeyError: Если отсутствует колонка `'category'`.
        """
        df = self.targetAllocator.AllocationTable
        df = df[df['category'] == 'stock']
        return df['Стоимость_source'].sum()
    
    def bonds_sum(self):
        """
        Сумма стоимости позиций в категории `'bonds'`.

        :returns: Сумма `'Стоимость_source'` для `category == 'bonds'`.
        :rtype: float
        :raises KeyError: Если отсутствует колонка `'category'`.
        """
        df = self.targetAllocator.AllocationTable
        df = df[df['category'] == 'bonds']
        return df['Стоимость_source'].sum()
    
    @staticmethod
    def sell_buy_string(row):
        """
        Формирует читаемую строку операции: покупка/продажа + лоты + сумма.

        :param row: Строка DataFrame с колонками `'lot number'`, `'delt расчет_calc'`.
        :type row: pd.Series
        :returns: Строка вида `"buy 10 шт. (5000 руб.)"` или `"-"`.
        :rtype: str
        :raises KeyError: Если отсутствуют ожидаемые колонки.
        """
        if row['lot number'] > 0:
            return f'buy {round(row['lot number'])} шт. ({round(row['delt расчет_calc'])} руб.)'
        elif row['lot number'] < 0:
            return f'sell {abs(round(row['lot number']))} шт. ({round(row['delt расчет_calc'])} руб.)'
        else: return '-'

    def distrib_of_money_string(self, df:pd.DataFrame):
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