import pandas as pd
from .table_splitter import TableSplitter
from io import StringIO


class SberSplitter(TableSplitter):
    """
    Класс для извлечения таблиц из HTML-отчёта Сбербанка.

    Использует `pandas.read_html` для парсинга всех таблиц в документе.
    Каждая таблица сохраняется в словарь под числовым ключом (порядковый номер).

    .. note::
        - Названия таблиц не извлекаются — используется индексация (0, 1, 2...).
        - Требуется корректная кодировка UTF-8.
        - Результат сохраняется в `self.df_dict`.

    Пример использования:
        splitter = SberSplitter()
        tables = splitter.split("report.html")
        splitter.save_excel("output.xlsx")  # если метод реализован в TableSplitter
    """
    def split(
            self,
            html_path:str
        ) -> dict[str, pd.DataFrame]:
        """
        Извлекает все HTML-таблицы из файла и возвращает их в виде словаря.

        :param html_path: Путь к HTML-файлу с отчётом.
        :type html_path: str

        :returns: Словарь, где ключ — индекс таблицы (int, начиная с 0),
                  значение — pandas.DataFrame с содержимым таблицы.
        :rtype: Dict[int, pd.DataFrame]

        :raises FileNotFoundError: Если файл не найден.
        :raises UnicodeDecodeError: Если файл не может быть прочитан в кодировке UTF-8.
        :raises ValueError: Если в HTML-файле не найдено ни одной таблицы.
        """
        df_dict = {}
        html_content = None
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        tables = pd.read_html(StringIO(html_content))
        for i, table in enumerate(tables):
            df_dict[i] = table
        self.df_dict = df_dict
        return df_dict
    
if __name__ == '__main__':
    splitter = SberSplitter()
    splitter.split(r'./.reports/400LSUS_11082025.html')
    splitter.save_excel(r'./.output/sber_splitter.xlsx')
