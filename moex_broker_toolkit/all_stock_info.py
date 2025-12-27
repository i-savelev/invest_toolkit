import pandas as pd


class AllStockInfo:
    """
    Загрузчик справочной информации по ценным бумагам из CSV-файла.

    Ожидается CSV-файл **без стандартного заголовка**, где:
    - строки 0 и 1 — служебные (например, дата, источник),
    - строка 2 — фактические названия столбцов,
    - данные начинаются со строки 3.

    Пример структуры файла:
        Справочник ЦБ;ВТБ Капитал Торговля;2025-08-22
        ;
        ISIN;SECID;SHORTNAME;LOTSIZE;...
        RU000A0JR2K7;SBER;Сбербанк ао;10;...
        ...

    После загрузки DataFrame сохраняется в `self.all_stock_df`.

    Атрибуты:
        all_stock_df: pandas.DataFrame со справочными данными по инструментам.
                      Ожидается наличие ключевых столбцов: 'ISIN', 'SECID', 'SHORTNAME', 'LOTSIZE'.
    """
    def __init__(
            self, 
            path:str
            ):
        """
        Инициализирует загрузчик и сразу читает CSV-файл.

        :param path: Путь к CSV-файлу со справочником.
        :type path: str

        :raises FileNotFoundError: Если файл не найден.
        :raises pd.errors.EmptyDataError: Если файл пуст.
        :raises pd.errors.ParserError: При неверном формате CSV (например, несовпадение `sep=';'`).
        :raises IndexError: Если в файле меньше 3 строк (нет строки с заголовками).
        """
        self.all_stock_df = self.get_all_stock_df(path)

    def get_all_stock_df(
            self, 
            path_csv:str
            ) -> pd.DataFrame:
        """Читает и обрабатывает CSV-файл со справочником инструментов.

        1. Читает файл без заголовка (`header=None`).
        2. Использует третью строку (`iloc[2]`) как заголовки.
        3. Удаляет первые три строки (0, 1, 2).
        4. Сбрасывает индекс.

        :param path_csv: Путь к CSV-файлу.
        :type path_csv: str

        :returns: Обработанный DataFrame со справочными данными.
        :rtype: pd.DataFrame

        :raises FileNotFoundError: Если файл не существует.
        :raises pd.errors.ParserError: При ошибках парсинга (например, не тот разделитель).
        :raises IndexError: Если файла < 3 строк.
        :raises UnicodeDecodeError: При несовместимости кодировки (ожидается UTF-8).
        """
        source_df = pd.read_csv(
            path_csv, 
            header=None,
            encoding='utf-8', 
            sep=';'
            )
        header = source_df.iloc[2]
        source_df.columns = header
        source_df.drop([0, 1, 2], axis = 0, inplace=True)
        df = source_df.reset_index(drop=True)
        df = pd.DataFrame(df)
        return df