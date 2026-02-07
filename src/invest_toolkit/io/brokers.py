import pandas as pd
from io import StringIO
from typing import Dict, Any
from invest_toolkit.utils import log
import os

COLUMNS_TO_KEEP = [
    'isin',
    'count',
    ]

def _split_vtb_report(excel_path:str) -> Dict[int, pd.DataFrame]:
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
    log.info(f"Начало обработки исходного отчёта ВТБ: {excel_path}...")
    try:
        log.debug(f"Чтение листа 'brokerage_report' из файла: {excel_path}")
        df = pd.read_excel(
            excel_path, 
            sheet_name="brokerage_report", 
            header=None
        )
        log.debug(f"Файл Excel успешно прочитан. Форма данных: {df.shape}")
        if df.empty:
            log.error("Лист 'brokerage_report' пуст.")
    except Exception as e:
        log.error(f"Ошибка при чтении файла: {e}")
    df_dict = {}
    current_table = []
    section_count = 0
    log.debug(f"Начало разбора строк отчёта. Всего строк: {len(df)}")
    
    for index, row in df.iterrows():
        if row.isna().all():
            if current_table:
                df_section = pd.DataFrame(current_table)
                df_cleaned = df_section.dropna(axis=1, how='all')
                
                if df_cleaned.empty:
                    log.warning(f"Секция {section_count} пуста после удаления пустых столбцов.")
                else:   
                    df_dict[section_count] = df_cleaned
                    log.debug(f"Секция {section_count} сохранена")       
                current_table = []
                section_count += 1
        else:
            current_table.append(row.values)
    
    # Обработка последней секции, если она не закончилась пустой строкой
    if current_table:
        log.debug(f"Обработка последней секции {section_count} (без завершающей пустой строки)")
        df_section = pd.DataFrame(current_table)
        df_cleaned = df_section.dropna(axis=1, how='all')
        
        if df_cleaned.empty:
            log.warning(f"Последняя секция {section_count} пуста после удаления пустых столбцов.")
        else:
            df_dict[section_count] = df_cleaned
            log.debug(f"Последняя секция {section_count} сохранена")
            
    
    log.info(f"Разделение отчёта ВТБ завершено. Извлечено {len(df_dict)} таблиц.")
    return df_dict

def read_vtb(excel_path:str):
    """
    Переопределяет метод в BrokerParser. Далее используется в get_balance_report_df() базового класса BrokerParser
    Извлекает и преобразует таблицу позиций из отчёта ВТБ.

    :returns: DataFrame с колонками, указанными в `COLUMNS_TO_KEEP` (обычно `['ISIN', 'Кол-во (шт)']`).
    :rtype: pd.DataFrame

    :raises KeyError: Если таблица `'Отчёт об остатках ценных бумаг'` отсутствует в `split_tables_dict`.
    :raises IndexError: 
        - Если после `iloc[1:-1]` таблица пуста,
        - Если `df.columns[0]` недоступен (пустые колонки),
        - Если `s.split(', ')` возвращает < 3 элементов в ISIN-колонке.
    :raises ValueError: 
        - Если `'Плановый исходящий остаток (шт)'` содержит нечисловые значения,
        - При ошибке приведения к числу после фильтра.
    :raises AttributeError: Если `COLUMNS_TO_KEEP` не определён или `RENAME_DICT_VTB` некорректен.
    """
    log.info("Начата обработка отчёта ВТБ...")
    log.debug("Извлечение исходной таблицы по ключу 7.")
    source_df = _split_vtb_report(excel_path)[7]
    log.debug(f"Исходная таблица получена. Форма: {source_df.shape}")
    
    df = source_df.iloc[1:-1].reset_index(drop=True)
    log.debug("Удалены первая и последняя строка. Установлена новая нумерация индексов.")
    
    df.columns = df.iloc[0]
    log.debug("Заголовки столбцов установлены по первой строке данных.")
    
    df = df[1:]
    df = df.reset_index(drop=True)
    log.debug("Удалена строка с заголовками из тела данных. Установлена новая нумерация индексов.")
    
    df.columns = df.columns.str.replace('\n', ' ', regex=False)
    log.debug("Символы переноса строки в названиях столбцов заменены на пробелы.")
    
    df = df[df['Плановый исходящий остаток (шт)']>0]
    log.debug("Выполнена фильтрация: оставлены только строки с положительным количеством.")
    
    first_col = df.columns[0]
    mask = ~(
        df[first_col].notna() &
        df[df.columns[1:]].isna().all(axis=1)
    )
    df = df[mask].copy()
    log.debug(f"Применена маска для удаления строк-разделителей. Форма после фильтрации: {df.shape}")
    
    df = df.rename(columns={
        'Наименование ценной бумаги, № гос. регистрации, ISIN': 'isin',
        'Плановый исходящий остаток (шт)': 'count', 
        })
    log.debug("Столбцы переименованы в 'isin' и 'count'.")
    
    df = df[COLUMNS_TO_KEEP]
    log.debug(f"Отобраны только необходимые колонки: {COLUMNS_TO_KEEP}")
    
    df['isin'] = df['isin'].apply(lambda s: s.split(', ')[2])
    log.debug("Извлечён ISIN из третьей части строки в столбце 'isin'.")
    log.info("Обработка отчёта ВТБ завершена.")
    return df

def _split_sber_report(html_path: str) -> Dict[int, pd.DataFrame]:
    """
    Извлекает все HTML-таблицы из отчёта Сбербанка и возвращает их в виде словаря.

    :param html_path: Путь к HTML-файлу с отчётом Сбербанка.
    :type html_path: str

    :returns: Словарь, где ключ — индекс таблицы (начиная с 0),
              значение — pandas.DataFrame с содержимым таблицы.
    :rtype: Dict[int, pd.DataFrame]

    :raises FileNotFoundError: Если файл по указанному пути не найден.
    :raises UnicodeDecodeError: Если файл не может быть прочитан в кодировке UTF-8.
    :raises ValueError: Если в HTML-файле не найдено ни одной таблицы.
    """
    log.info(f"Начало обработки исходного отчёта Сбербанка: {html_path}...")
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        log.debug(f"Файл отчёта успешно прочитан. Размер: {len(html_content)} символов")
        
        tables = pd.read_html(StringIO(html_content))
        log.info(f"Найдено таблиц: {len(tables)}")
        
        df_dict = {}
        for i, table in enumerate(tables):
            df_dict[i] = table
            log.debug(f"Таблица {i}: {table.shape[0]} строк, {table.shape[1]} столбцов")
            
        log.info("Обработка отчёта Сбербанка завершена.")
        return df_dict
    
    except Exception as e:
        log.critical(f"Неожиданная ошибка при обработке отчёта Сбербанка: {e}")
        raise

def read_sber(html_path: str)->pd.DataFrame:
    """
    Извлекает и преобразует таблицу позиций из отчёта Сбербанка.

    Таблица берётся из `self.split_tables_dict[2]` и проходит следующие этапы:
    - установка первой строки как временных имён столбцов,
    - фильтрация по двум ключевым колонкам,
    - установка второй строки как финальных имён столбцов,
    - обрезка "служебных" строк (первые 4 и последние 3),
    - переименование согласно `RENAME_DICT_SBER`,
    - преобразование колонки `'Кол-во (шт)'` в `float` (удаление пробелов в числах),
    - отбор только нужных колонок (`self.COLUMNS_TO_KEEP`).

    :returns: Обработанный DataFrame с позициями портфеля.
    :rtype: pd.DataFrame

    :raises KeyError: Если в `split_tables_dict` нет ключа `2`,
                      или отсутствуют ожидаемые колонки (`'Основной рынок'`, `'Плановые показатели'`).
    :raises IndexError: Если в таблице недостаточно строк (например, < 5 строк после фильтрации).
    :raises AttributeError: Если `self.COLUMNS_TO_KEEP` не определён в подклассе или экземпляре.
    :raises ValueError: При ошибке приведения `'Плановый исходящий остаток, шт'` к `float`.
    """
    log.info("Начата обработка отчёта Сбербанка...")
    log.debug("Извлечение исходной таблицы по ключу 2.")
    df:pd.DataFrame = _split_sber_report(html_path)[2]
    log.debug(f"Исходная таблица получена. Форма: {df.shape}")
    log.debug(f"Исходная таблица получена. Столбцы: {df.columns.names}")
    
    df.columns = df.iloc[0]
    log.debug("Заголовки столбцов установлены по первой строке данных.")
    
    df = df[
            [
            'Основной рынок',
            'Плановые показатели'
            ]
        ]
    log.debug("Выполнена фильтрация таблицы по ключевым колонкам: 'Основной рынок', 'Плановые показатели'.")
    
    df.columns = df.iloc[1]
    log.debug("Заголовки столбцов обновлены по второй строке данных.")
    
    df = df.iloc[4:-3].reset_index(drop=True)
    log.debug("Удалены первые 4 и последние 3 служебные строки. Установлена новая нумерация индексов.")
    
    df = df.rename(columns={
        'ISIN ценной бумаги': 'isin',
        'Количество, шт': 'count',
    })
    log.debug("Столбцы переименованы в 'isin' и 'count'.")
    
    df['count'] = df['Плановый исходящий остаток, шт'].str.replace(' ', '').astype(float)
    log.debug("Столбец 'Плановый исходящий остаток, шт' преобразован в числовое значение.")
    
    df = df[COLUMNS_TO_KEEP]
    log.debug(f"Отобраны только необходимые колонки: {COLUMNS_TO_KEEP}")
    log.info("Обработка отчёта Сбербанка завершена.")
    return df

def _save_tables_to_excel(tables: Dict[int, pd.DataFrame], output_path: str) -> None:
    """
    Сохраняет словарь таблиц в Excel-файл (по одной таблице на лист).

    :param tables: Словарь с таблицами (ключ — индекс, значение — DataFrame).
    :type tables: Dict[int, pd.DataFrame]
    :param output_path: Путь к выходному Excel-файлу (.xlsx).
    :type output_path: str

    :raises OSError: Если невозможно записать файл (нет прав, путь некорректен).
    :raises ValueError: Если движок 'openpyxl' недоступен или файл повреждён.
    :raises AttributeError: Если `tables` не является словарём.
    """
    log.info(f"Сохранение таблиц в Excel: {output_path}")
    
    if not isinstance(tables, dict):
        log.error("tables должен быть словарём")
        raise AttributeError("tables должен быть словарём")
    
    if not tables:
        log.warning("Словарь таблиц пуст. Файл не будет создан.")
        return
    
    try:
        # Создаем родительскую директорию, если она не существует
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            log.info(f"Создана директория для сохранения: {output_dir}")

        with pd.ExcelWriter(output_path, mode='w', engine='openpyxl') as writer:
            for i, (key, df) in enumerate(tables.items()):
                sheet_name = f"{i}"
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                log.debug(f"Сохранён лист '{sheet_name}': {df.shape[0]}x{df.shape[1]}")
        log.info("Сохранение в Excel успешно завершено.")
    except Exception as e:
        log.critical(f"Неожиданная ошибка при сохранении Excel: {e}")
        raise
        
if __name__ == '__main__':
    # Пример использования
    log.init(f'Test {__file__}')
    report_path_sber = r'./.reports/sber_09102025.HTML'  # Пример пути
    output_excel_sber = r'./.output/sber_tables.xlsx'
    report_path_vtb = r'./.reports/vtb_20250917_20251012.xlsx'  # Пример пути
    output_excel_vtb = r'./.output/vtb_tables.xlsx'
    
    # tables_sber = _split_sber_report(report_path_sber)
    # _save_tables_to_excel(tables_sber, output_excel_sber)
    # log.separator()
    # tables_vtb = _split_vtb_report(report_path_vtb)
    # _save_tables_to_excel(tables_vtb, output_excel_vtb)
    
    sber = read_sber(report_path_sber)
    log.raw_dataframe(caption='Очищенные данные сбера', df=sber)
    vtb = read_vtb(report_path_vtb)
    log.raw_dataframe(caption='Очищенные данные ВТБ', df=vtb)