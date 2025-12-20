import pandas as pd
from .table_splitter import TableSplitter

class VtbSplitter(TableSplitter):
    """
    Класс для разделения отчёта ВТБ (Excel-файл) на отдельные логические таблицы.

    Отчёт ожидается в виде одного листа ('brokerage_report') без заголовков (header=None),
    где таблицы разделены пустыми строками. Первая ячейка каждой таблицы (после пропуска пустых строк)
    интерпретируется как её название.

    Пример структуры Excel:
        [таблица_1_заголовок]
        [данные]
        [данные]
        [пустая строка]
        [таблица_2_заголовок]
        ...

    .. note::
        Класс сохраняет результат в атрибут `self.df_dict` и возвращает его из метода `split`.

    Пример использования:
        splitter = VtbSplitter()
        tables = splitter.split("report.xlsx")
        splitter.save_excel("output.xlsx")  # если реализовано в TableSplitter
    """
    def split(
            self, 
            excel_path:str,
        ) -> dict[int, pd.DataFrame]:
        """
        Разделяет Excel-файл отчёта ВТБ на отдельные таблицы по пустым строкам.

        :param excel_path: Путь к Excel-файлу с отчётом.
        :type excel_path: str

        :returns: Словарь, где ключ — название таблицы (значение первой ячейки),
                  значение — DataFrame этой таблицы без полностью пустых столбцов.
        :rtype: Dict[str, pd.DataFrame]

        :raises FileNotFoundError: Если файл по указанному пути не найден.
        :raises ValueError: Если лист 'brokerage_report' отсутствует или пуст.
        :raises IndexError: Если в какой-либо секции отсутствует строка с названием таблицы
                            (например, пустая секция без данных).
        """
        df = pd.read_excel(
            excel_path, 
            sheet_name="brokerage_report", 
            header=None
            )
        df_dict = {}
        current_table = []
        for index, row in df.iterrows():
            if row.isna().all():
                if current_table:
                    df = pd.DataFrame(current_table)
                    df_cleaned = df.dropna(axis=1, how='all')
                    table_name = df_cleaned.iloc[0, 0]
                    df_dict[table_name] = df_cleaned
                    current_table = []
            else:
                current_table.append(row.values)
        if current_table:
            df = pd.DataFrame(current_table)
            df_cleaned = df.dropna(axis=1, how='all')
            table_name = df_cleaned.iloc[0, 0]
            df_dict[table_name] = df_cleaned
        self.df_dict = df_dict
        return df_dict
    
if __name__ == '__main__':
    splitter = VtbSplitter()
    dict = splitter.split(r'./.reports/vtb20250818_20250821.xlsx')
    splitter.save_excel(r'./.output/vtb_splitter.xlsx')
    for key in dict.keys():
        print(key)