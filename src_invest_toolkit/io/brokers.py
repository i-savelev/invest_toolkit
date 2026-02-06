import pandas as pd
from io import StringIO
from typing import Dict, Any
import sys
import os
# Добавляем путь к корню проекта, чтобы можно было импортировать модуль logger
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from logger.logger import Logger


def split_sber_report(html_path: str) -> Dict[int, pd.DataFrame]:
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
    Logger.info(f"Начало обработки отчёта Сбербанка: {html_path}", name="io.brokers.sber")
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        Logger.debug(f"Файл отчёта успешно прочитан. Размер: {len(html_content)} символов", name="io.brokers.sber")
        
        tables = pd.read_html(StringIO(html_content))
        Logger.info(f"Найдено таблиц: {len(tables)}", name="io.brokers.sber")
        
        df_dict = {}
        for i, table in enumerate(tables):
            df_dict[i] = table
            Logger.debug(f"Таблица {i}: {table.shape[0]} строк, {table.shape[1]} столбцов", name="io.brokers.sber")
            
        Logger.info("Обработка отчёта Сбербанка завершена.", name="io.brokers.sber")
        return df_dict
        
    except FileNotFoundError:
        Logger.error(f"Файл не найден: {html_path}", name="io.brokers.sber")
        raise
    except UnicodeDecodeError as e:
        Logger.error(f"Ошибка декодирования UTF-8: {e}", name="io.brokers.sber")
        raise
    except ValueError as e:
        if "No tables found" in str(e):
            Logger.error(f"В HTML-файле не найдено ни одной таблицы.", name="io.brokers.sber")
        else:
            Logger.error(f"Ошибка при парсинге таблиц: {e}", name="io.brokers.sber")
        raise
    except Exception as e:
        Logger.critical(f"Неожиданная ошибка при обработке отчёта Сбербанка: {e}", name="io.brokers.sber")
        raise


def save_tables_to_excel(tables: Dict[int, pd.DataFrame], output_path: str) -> None:
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
    Logger.info(f"Сохранение таблиц в Excel: {output_path}", name="io.brokers.sber")
    
    if not isinstance(tables, dict):
        Logger.error("tables должен быть словарём", name="io.brokers.sber")
        raise AttributeError("tables должен быть словарём")
    
    if not tables:
        Logger.warning("Словарь таблиц пуст. Файл не будет создан.", name="io.brokers.sber")
        return
    
    try:
        # Создаем родительскую директорию, если она не существует
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            Logger.info(f"Создана директория для сохранения: {output_dir}", name="io.brokers.sber")

        with pd.ExcelWriter(output_path, mode='w', engine='openpyxl') as writer:
            for i, (key, df) in enumerate(tables.items()):
                sheet_name = f"{i}"
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                Logger.debug(f"Сохранён лист '{sheet_name}': {df.shape[0]}x{df.shape[1]}", name="io.brokers.sber")
        Logger.info("Сохранение в Excel успешно завершено.", name="io.brokers.sber")
        
    except OSError as e:
        Logger.error(f"Ошибка записи файла: {e}", name="io.brokers.sber")
        raise
    except Exception as e:
        Logger.critical(f"Неожиданная ошибка при сохранении Excel: {e}", name="io.brokers.sber")
        raise
        
if __name__ == '__main__':
    # Пример использования
    Logger.init('# Пример использования')
    report_path = r'./.reports/sber_01012026_31012026.HTML'  # Пример пути
    output_excel = r'./.output/sber_tables.xlsx'
    
    try:
        tables = split_sber_report(report_path)
        save_tables_to_excel(tables, output_excel)
    except Exception as e:
        Logger.critical(f"Фатальная ошибка в примере использования: {e}", name="io.brokers.sber")