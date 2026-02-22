import pandas as pd
from io import StringIO
from typing import Dict, Any
from invest_toolkit.utils import log
from invest_toolkit.utils import log_dataframe
import os

COLUMNS_TO_KEEP = [
    'isin',
    'count_pieces',
    ]

def _split_vtb_report(excel_path:str) -> Dict[int, pd.DataFrame]:
    """Разделяет Excel-файл отчёта ВТБ на отдельные таблицы по пустым строкам.

    :param excel_path: Путь к Excel-файлу с отчётом.
    :returns: Словарь {индекс_секции: DataFrame}.
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

@log_dataframe
def read_vtb(excel_path:str):
    """Извлекает и преобразует таблицу позиций из отчёта ВТБ.

    :param excel_path: Путь к Excel-файлу отчёта ВТБ.
    :returns: DataFrame с колонками: isin, count_pieces.
    """
    log.info("Начата обработка отчёта ВТБ...")
    log.debug("Извлечение исходной таблицы по ключу 6.")
    source_df = _split_vtb_report(excel_path)[6]
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
        'Плановый исходящий остаток (шт)': 'count_pieces', 
        })
    log.debug("Столбцы переименованы в 'isin' и 'count'.")
    
    df = df[COLUMNS_TO_KEEP]
    log.debug(f"Отобраны только необходимые колонки: {COLUMNS_TO_KEEP}")
    
    df['isin'] = df['isin'].apply(lambda s: s.split(', ')[2])
    log.debug("Извлечён ISIN из третьей части строки в столбце 'isin'.")
    log.info("Обработка отчёта ВТБ завершена.")
    return df

def _split_sber_report(html_path: str) -> Dict[int, pd.DataFrame]:
    """Извлекает все HTML-таблицы из отчёта Сбербанка.

    :param html_path: Путь к HTML-файлу с отчётом.
    :returns: Словарь {индекс_таблицы: DataFrame}.
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

@log_dataframe
def read_sber(html_path: str)->pd.DataFrame:
    """Извлекает и преобразует таблицу позиций из отчёта Сбербанка.

    :param html_path: Путь к HTML-файлу отчёта Сбербанка.
    :returns: DataFrame с колонками: isin, count_pieces.
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
        'Количество, шт': 'count_pieces',
    })
    log.debug("Столбцы переименованы в 'isin' и 'count_pieces'.")
    
    df['count_pieces'] = df['Плановый исходящий остаток, шт'].str.replace(' ', '').astype(float)
    log.debug("Столбец 'Плановый исходящий остаток, шт' преобразован в числовое значение.")
    
    df = df[COLUMNS_TO_KEEP]
    log.debug(f"Отобраны только необходимые колонки: {COLUMNS_TO_KEEP}")
    log.info("Обработка отчёта Сбербанка завершена.")
    return df

def save_tables_to_excel(tables: Dict[int, pd.DataFrame], output_path: str) -> None:
    """
    Сохраняет словарь таблиц в Excel-файл (по одной таблице на лист).

    :param tables: Словарь с таблицами (ключ — индекс, значение — DataFrame).
    :type tables: Dict[int, pd.DataFrame]
    :param output_path: Путь к выходному Excel-файлу (.xlsx).
    :type output_path: str
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