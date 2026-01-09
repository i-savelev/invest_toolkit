import pandas as pd
from typing import Optional
from .all_stock_info import AllStockInfo


class DistributionTable:
    """
    Генератор сводной таблицы распределения портфеля по категориям из Excel-шаблона.

    Ожидается Excel-файл со следующей структурой:
    - Лист `'categories'`: колонки `['category', '%']` — категории и их целевые доли (в %, сумма = 100).
    - Остальные листы: по одному на категорию; колонки `['ticker', '%']` — тикеры и их доли *внутри* категории (сумма = 100).
    
    Пример:
      categories:
        | category | %  |
        |----------|----|
        | Акции    | 60 |
        | Облигации| 40 |

      Акции:
        | ticker | %  |
        |--------|----|
        | SBER   | 50 |
        | GAZP   | 50 |

      → В итоге: SBER = 30%, GAZP = 30% от всего портфеля.

    Итоговая таблица обогащается данными из `AllStockInfo`: ISIN, название, размер лота.

    Атрибуты:
        file_path: Путь к Excel-файлу с распределением.
        df_dict: Словарь DataFrame-ов по листам Excel (заполняется в `_get_df_dict`).
        distribution_table: Итоговый DataFrame с абсолютными долями и метаданными.
        all_stock_df: Справочник инструментов (`AllStockInfo.all_stock_df`).
    """
    def __init__(
            self,
            file_path:str,
            all_stock_info: AllStockInfo,
            ):
        """
        Инициализирует DistributionTable.

        :param file_path: Путь к Excel-файлу с распределением.
        :param all_stock_info: Экземпляр справочника инструментов.
        """
        self.file_path = file_path
        self.df_dict:dict[str, pd.DataFrame]
        self.distribution_table:pd.DataFrame
        self.all_stock_df = all_stock_info.all_stock_df

    def _get_df_dict(self) -> dict[str, pd.DataFrame]:
        """
        Читает все листы Excel-файла и валидирует процентные суммы.

        - Для листа `'categories'`: проверяет, что сумма в колонке `'%'` = 100.
        - Для остальных листов: проверяет, что сумма `'%'` = 100 и есть колонка `'ticker'`.
        - Удаляет строки с `NaN` в ключевых колонках.

        :returns: Словарь: имя листа → DataFrame.
        :rtype: Dict[str, pd.DataFrame]

        :raises ValueError: 
            - Если сумма `'%'` ≠ 100 на каком-либо листе,
            - Если отсутствует колонка `'%'` или `'ticker'`/`'category'`.
        :raises FileNotFoundError: Если файл не найден.
        :raises KeyError: Если отсутствует лист `'categories'`.
        """
        df_dict = pd.read_excel(
            io=self.file_path,
            sheet_name=None,
        )
        for key in df_dict:
            if key == 'categories':
                df_dict[key].dropna(subset=['category'], inplace=True)
                self.percent_error(
                    df_dict[key],
                    100,
                    '%',
                    key
                )
            else:
                df_dict[key].dropna(subset=['ticker'], inplace=True)
                self.percent_error(
                    df_dict[key],
                    100,
                    '%',
                    key
                )
        self.df_dict = df_dict
        return df_dict
    
    @staticmethod
    def percent_error(df:pd.DataFrame, val: float, column:str, name:str):
        """Проверяет, что сумма значений в столбце равна ожидаемому значению.

        :param df: DataFrame для проверки.
        :param val: Ожидаемая сумма (обычно `100.0`).
        :param column: Имя столбца с процентами.
        :param name: Название листа/группы (для сообщения об ошибке).

        :raises ValueError: Если `df[column].sum()` ≠ `val` (с точностью до float).
        :raises KeyError: Если столбец `column` отсутствует.
        """
        sum = df[column].sum()
        if sum != val:
            raise ValueError(f'сумма процентов {name} равна {sum}, а не равно 100%')

    def get_table(self):
        """
        Формирует итоговую таблицу распределения портфеля с обогащёнными данными.

        1. Загружает и валидирует листы через `_get_df_dict()`.
        2. Для каждого листа (кроме `'categories'`):
           - находит его долю в `categories`,
           - масштабирует внутренние `%` до абсолютной доли портфеля,
           - добавляет колонку `category`.
        3. Объединяет все таблицы.
        4. Для каждого тикера добавляет:
           - `ISIN`, `Размер лота`, `name` — из `all_stock_df`.

        :returns: Итоговый DataFrame с колонками:
                  `ticker`, `%`, `category`, `ISIN`, `Размер лота`, `name`.
        :rtype: pd.DataFrame

        :raises KeyError: 
            - Если лист отсутствует в `categories`,
            - Если `'categories'` не содержит колонку `'%'` или `'category'`.
        :raises IndexError: 
            - Если тикер не найден в `all_stock_df`,
            - Если по категории найдено ≠1 записи в `categories_df`.
        :raises ValueError: При ошибке приведения `'Размер лота'` к `float`.
        """
        self._get_df_dict()
        categories_df = self.df_dict['categories']
        categories_list = categories_df['category'].tolist()
        df_list:list[pd.DataFrame] = []
        for key in self.df_dict:
            if key != 'categories':
                if key in categories_list:
                    df:pd.DataFrame = self.df_dict[key]
                    category_percent = categories_df.loc[
                        categories_df['category'] == key, 
                        '%'
                        ].iloc[0]
                    df_copy = df.copy()
                    df_copy['%'] = category_percent/100*df['%'].round(10)
                    df_copy['category'] = key
                    df_list.append(df_copy)
                else: raise Exception(f'листа {key} нет в категориях')
        self.distribution_table = pd.concat(df_list).reset_index(drop=True)
        for index, row,  in self.distribution_table.iterrows():
            id = row['ticker']
            isin = self.all_stock_df.loc[
                self.all_stock_df['SECID'] == id, 
                'ISIN'
                ].iloc[0]
            lot_size = self.all_stock_df.loc[
                self.all_stock_df['SECID'] == id, 
                'LOTSIZE'
                ].iloc[0]
            shortname = self.all_stock_df.loc[
                self.all_stock_df['SECID'] == id, 
                'SHORTNAME'
                ].iloc[0]
            self.distribution_table.at[index, "ISIN"] = isin
            self.distribution_table.at[index, "Размер лота"] = lot_size
            self.distribution_table.at[index, "name"] = shortname
        self.distribution_table["Размер лота"] = self.distribution_table["Размер лота"].astype('float')
        return self.distribution_table

    
if __name__ == '__main__':
    ds = DistributionTable(r'./.support_files/index_fund.xlsx')
    d = ds._get_df_dict()
    print(ds.get_table())