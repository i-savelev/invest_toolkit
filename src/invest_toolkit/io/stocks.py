import pandas as pd
from typing import List, Set, Optional, Dict
from pathlib import Path
import re
from invest_toolkit.utils import log, log_dataframe

def _clean_numeric(value: str) -> Optional[float]:
    """
    Преобразует строковое значение в число, обрабатывая форматы:
    - Пробелы в тысячах: "1 046" → 1046.0
    - Запятые как десятичный разделитель: "0,15" → 0.15
    - Пустые значения → NaN
    
    :param value: Строковое значение для преобразования
    :returns: Число float или None если преобразование невозможно
    """
    if pd.isna(value) or value == '' or value == ';':
        return None
    
    # Удаляем кавычки и лишние пробелы
    value = str(value).strip().strip('"').strip("'").strip()
    
    if not value:
        return None
    
    # Обработка процентов: "17.9%" → 17.9
    is_percent = False
    if value.endswith('%'):
        is_percent = True
        value = value.rstrip('%').strip()
    
    # Заменяем запятые на точки для десятичных дробей
    # Но сначала удаляем пробелы-разделители тысяч
    value = value.replace(' ', '').replace('\xa0', '')
    
    # Если есть запятая и нет точки — это десятичный разделитель
    if ',' in value and '.' not in value:
        value = value.replace(',', '.')
    # Если есть и запятая, и точка — запятая разделитель тысяч (удаляем)
    elif ',' in value and '.' in value:
        value = value.replace(',', '')
    
    try:
        num = float(value)
        return num
    except ValueError:
        return None


def _extract_ticker_from_filename(filename: str) -> str:
    """
    Извлекает тикер из имени файла (например, 'VTBR.csv' → 'VTBR').
    
    :param filename: Имя файла
    :returns: Тикер или имя файла без расширения
    """
    stem = Path(filename).stem
    # Удаляем возможные суффиксы вроде '_download'
    match = re.match(r'^([A-Z0-9]+)', stem)
    return match.group(1) if match else stem


def parse_financial_csv(file_path: Path) -> pd.DataFrame:
    """
    Парсит CSV файл с финансовой отчётностью в структурированный формат.
    
    :param file_path: Путь к CSV файлу
    :returns: DataFrame с колонками: [ticker, filename, показатель, год, значение]
    :raises ValueError: При ошибках чтения или парсинга
    """
    if not file_path.exists():
        raise ValueError(f"Файл не найден: {file_path}")
    
    try:
        # Читаем "как есть" для анализа структуры
        df_raw = pd.read_csv(file_path, sep=';', header=None, dtype=str, na_filter=False)
    except Exception as e:
        log.error(f"Ошибка чтения {file_path}: {e}")
        raise ValueError(f"Ошибка чтения {file_path}: {e}")
    
    if df_raw.empty:
        return pd.DataFrame()
    
    # Определяем первую строку с годами (обычно содержит цифры 4-значные)
    year_row_idx = None
    for idx, row in df_raw.iterrows():
        # Ищем строку, где есть значения вида "2008", "2024" и т.д.
        if any(re.match(r'^\d{4}$', str(cell).strip()) for cell in row[1:] if pd.notna(cell)):
            year_row_idx = idx
            break
    
    if year_row_idx is None:
        raise ValueError(f"Не найдена строка с годами в файле {file_path}")
    
    # Годы начинаются со второго столбца (первый — название показателя)
    years = [str(cell).strip() for cell in df_raw.iloc[year_row_idx, 1:] if pd.notna(cell) and cell != '' and cell != 'LTM']
    
    if not years:
        return pd.DataFrame()
    
    # Собираем данные
    records = []
    ticker = _extract_ticker_from_filename(file_path.name)
    
    # Обрабатываем строки ниже строки с годами
    for row_idx in range(year_row_idx + 1, len(df_raw)):
        row = df_raw.iloc[row_idx]
        indicator = str(row[0]).strip().strip('"').strip("'")
        
        # Пропускаем пустые показатели
        if not indicator or indicator.lower() in ['nan', '']:
            continue
        
        # Обрабатываем значения по годам
        for col_idx, year in enumerate(years, start=1):
            if col_idx >= len(row):
                break
            
            raw_value = row[col_idx]
            if pd.isna(raw_value) or raw_value == '':
                raw_value = '0'
            
            numeric_value = _clean_numeric(raw_value)
            if numeric_value is not None:
                records.append({
                    'ticker': ticker,
                    'indicator': indicator,
                    'year': year,
                    'value': numeric_value
                })
    return pd.DataFrame(records)

@log_dataframe
def merge_csv_files(directory: str) -> pd.DataFrame:
    """
    Объединяет все CSV файлы из директории в единый DataFrame.
    
    :param directory: Путь к директории с CSV файлами
    :param pattern: Шаблон поиска файлов (по умолчанию '*.csv')
    :returns: Объединённый DataFrame с колонками:
              [ticker, filename, indicator, year, value]
    :raises ValueError: При ошибках обработки
    """
    log.info(f'Объединение данных из папки {directory}...')
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        log.error(f"Директория не найдена: {directory}")
        raise ValueError(f"Директория не найдена: {directory}")
    
    csv_files = list(dir_path.glob('*.csv'))
    if not csv_files:
        log.error(f"Не найдено CSV файлов по шаблону '*.csv' в {directory}")
        raise ValueError(f"Не найдено CSV файлов по шаблону '*.csv' в {directory}")
    
    print(f"Найдено файлов: {len(csv_files)}")
    log.info(f"Найдено файлов: {len(csv_files)}")
    all_data = []
    
    for file_path in sorted(csv_files):
        try:
            df = parse_financial_csv(file_path)
            if not df.empty:
                all_data.append(df)
            else:
                log.warning(f"⚠ {file_path.name:20s} → пустой")
        except Exception as e:
            log.error(f"✗ {file_path.name:20s} → ошибка: {e}")
            continue
    
    if not all_data:
        return pd.DataFrame(columns=['ticker', 'filename', 'indicator', 'year', 'value'])
    
    merged_df:pd.DataFrame = pd.concat(all_data, ignore_index=True)
    
    # Преобразуем числовые значения где возможно
    merged_df['value'] = pd.to_numeric(merged_df['value'], errors='coerce')

    
    print(f"\n✅ Объединено: {len(merged_df)} записей из {len(all_data)} файлов")
    print(f"   Уникальных тикеров: {merged_df['ticker'].nunique()}")
    print(f"   Уникальных показателей: {merged_df['indicator'].nunique()}")
    log.info(f"✅ Объединено: {len(merged_df)} записей из {len(all_data)} файлов")
    log.info(f"Уникальных тикеров: {merged_df['ticker'].nunique()}")
    log.info(f"Уникальных показателей: {merged_df['indicator'].nunique()}")
    log.info(f"Годы: {sorted(merged_df['year'].unique())}")
    log.info(f"Уникальные показатели: {merged_df['indicator'].unique().tolist()}")
    return merged_df

@log_dataframe
def free_float(path:str):
    """
    Источник данных для free-float:
    https://www.moex.com/ru/listing/free-float.aspx

    В таблцу вручную добавляется SIBN = 0.045

    :param path: Описание
    :type path: str
    """
    log.info(f'Получение free-float из {path}...')
    df = pd.read_excel(path)
    df.rename(columns={
        'Код':'ticker',
        'Коэффициент free-float, %':'value',
    }, inplace=True)
    df.drop(columns=[
        'Полное наименование организации',
        'ИНН организации',
        'Тип инструмента',
        'Регистрационный номер выпуска / ISIN',
        'Уровень листинга',
    ], inplace=True)
    df['indicator'] ='free_float'
    df['value'] = df['value']/100
    return df

@log_dataframe
def ir_rating(path:str):
    """
    Источник данных:
    https://sl-rating.ru/?rating

    """
    log.info(f'Получение free-float из {path}...')
    df = pd.read_excel(path)
    df.drop(columns=[
        'name',
    ], inplace=True)
    df['value'] = df['value']/100
    return df

if __name__=='__main__':
    log.init(f'TEST {__file__}')
    df = parse_financial_csv(file_path=Path(r'./.output/test_scrapper/SBER.csv'))
    print(df)
    merge_csv_files(directory=r'./support_files/scrapper_reports')

