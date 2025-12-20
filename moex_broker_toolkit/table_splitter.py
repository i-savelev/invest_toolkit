import pandas as pd
from typing import Optional

class TableSplitter:
    """
    Базовый класс для разделения табличных отчётов на логические таблицы.

    Хранит результат разделения в атрибуте `df_dict` (словарь: имя → DataFrame).
    Предназначен для наследования: подклассы (например, `VtbSplitter`, `SberSplitter`)
    должны переопределять метод `split`.

    Атрибуты:
        df_dict: Словарь с извлечёнными таблицами. Ключ — строковое имя таблицы,
                 значение — pandas.DataFrame. Инициализируется пустым словарём.
    """
    def __init__(self):
        """
        Инициализирует TableSplitter с пустым словарём таблиц.
        """
        self.df_dict: dict[str, pd.DataFrame] = {}

    def split(self) -> dict[str, pd.DataFrame]:
        """
        Разделяет входной отчёт на отдельные таблицы.

        Базовая реализация возвращает пустой словарь.
        Должна быть переопределена в подклассах.

        :returns: Словарь с таблицами. По умолчанию — пустой.
        :rtype: Dict[str, pd.DataFrame]
        """
        return {}
    
    def save_excel(
            self,
            output_path:str
        ) -> None:
        """
        Сохраняет все таблицы из `self.df_dict` в Excel-файл (по одной на лист).

        Таблицы сохраняются на отдельных листах с именами вида '0', '1', '2', и т.д.
        Индекс DataFrame не включается в файл.

        :param output_path: Путь к выходному Excel-файлу (.xlsx).
        :type output_path: str

        :raises OSError: Если невозможно записать файл (например, нет прав или путь некорректен).
        :raises ValueError: Если движок 'openpyxl' недоступен или файл повреждён.
        :raises AttributeError: Если `self.df_dict` не является словарём (например, был перезаписан).

        .. note::
            Если `self.df_dict` пуст или `None`, выводится сообщение 'empty dataframe dict',
            и файл **не создаётся** (ExcelWriter не инициализируется).
        """
        if self.df_dict is not None:
            with pd.ExcelWriter(
                output_path, 
                mode='w', 
                engine='openpyxl'
                ) as writer:
                for i, key in enumerate(self.df_dict):
                    self.df_dict[key].to_excel(
                        writer, 
                        sheet_name=f'{i}', 
                        index=False
                        )
        else: print('empty dataframe dict')
    
if __name__ == '__main__':
    tb = TableSplitter()
    tb.save_excel(r'../.output/test.xlsx')