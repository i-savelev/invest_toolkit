import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional, Dict
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict
import time
import pandas as pd
from pathlib import Path
import re


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
}

def get_tickers_with_selenium() -> Dict[str, str]:
    """
    Извлекает тикеры через рендеринг JavaScript с помощью Selenium.
    
    :returns: Словарь {тикер: ссылка}
    :raises Exception: При ошибках драйвера или таймауте
    """
    options = Options()
    options.add_argument('--headless')  # Запуск без открытия браузера
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    try:
        driver.get('https://smart-lab.ru/q/shares/')
        
        # Ждём загрузки таблицы (появления строк с атрибутом ticker)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[ticker]'))
        )
        
        # Дополнительная пауза для полной загрузки данных
        time.sleep(5)
        
        ticker_links = {}
        
        # Извлекаем все строки таблицы
        rows = driver.find_elements(By.CSS_SELECTOR, 'tr[ticker]')
        
        for row in rows:
            ticker = row.get_attribute('ticker')
            if ticker:
                # Находим ссылку на фундаментальный анализ
                try:
                    link_element = row.find_element(By.CSS_SELECTOR, 'a.charticon2')
                    href = link_element.get_attribute('href')
                    if href:
                        ticker_links[ticker] = href
                except:
                    continue
        
        print(f"✅ Получено {len(ticker_links)} тикеров через Selenium")
        return ticker_links
    
    finally:
        driver.quit()


def download_file_from_page(page_url: str, 
                           download_selector: str = 'a.download-table',
                           save_directory: str = './support_files/scrapper_reports',
                           file_name:str = '',
                           timeout: int = 30) -> Optional[str]:
    """
    Скачивает файл с указанной страницы по селектору кнопки.
    
    :param page_url: URL страницы с файлом для скачивания
    :param download_selector: CSS селектор для кнопки скачивания
    :param save_directory: Директория для сохранения файлов
    :param timeout: Таймаут запроса в секундах
    :returns: Путь к скачанному файлу или None если файл не найден
    :raises ValueError: Если параметры некорректные
    :raises requests.RequestException: При ошибках сети
    :raises requests.HTTPError: При ошибках HTTP
    """
    if not page_url or not isinstance(page_url, str):
        raise ValueError("page_url must be a non-empty string")
    
    if not download_selector or not isinstance(download_selector, str):
        raise ValueError("download_selector must be a non-empty string")
    
    try:
        os.makedirs(save_directory, exist_ok=True)
        
        response = requests.get(page_url, timeout=timeout, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        download_button = soup.select_one(download_selector)
        
        if not download_button:
            return None
            
        
        file_url = download_button.get('href')
        if not file_url:
            return None
        
        file_url = urljoin(page_url, file_url)
        
        file_response = requests.get(file_url, timeout=timeout, stream=True, verify=False)
        file_response.raise_for_status()
        
        filename = f"{file_name}.csv"

        file_path = os.path.join(save_directory, filename)
        
        with open(file_path, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return file_path
    
    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to download from {page_url}: {e}")


def get_random_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> float:
    """
    Генерирует случайную задержку в указанном диапазоне.
    
    :param min_delay: Минимальная задержка в секундах
    :param max_delay: Максимальная задержка в секундах
    :returns: Случайное значение задержки
    :raises ValueError: Если значения некорректны
    """
    if min_delay < 0 or max_delay < 0:
        raise ValueError("Delays must be non-negative")
    if min_delay > max_delay:
        raise ValueError("min_delay cannot be greater than max_delay")
    
    return random.uniform(min_delay, max_delay)


def apply_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> None:
    """
    Выполняет задержку с рандомизацией для вежливого скрапинга.
    
    :param min_delay: Минимальная задержка в секундах
    :param max_delay: Максимальная задержка в секундах
    """
    delay = get_random_delay(min_delay, max_delay)
    time.sleep(delay)


def scrape_and_download(
                       min_delay: float = 5,
                       max_delay: float = 10) -> Set[str]:
    """
    Обходит ссылки и скачивает файлы с рандомизированными задержками.
    
    :param base_url: URL базовой страницы
    :param link_selector: CSS селектор для фильтрации ссылок
    :param download_selector: CSS селектор кнопки скачивания
    :param save_directory: Директория для сохранения файлов
    :param request_timeout: Таймаут одного HTTP-запроса (сек)
    :param min_delay: Минимальная задержка между запросами (сек)
    :param max_delay: Максимальная задержка между запросами (сек)
    :returns: Множество путей к скачанным файлам
    """
    downloaded_files = set()
    links = get_tickers_with_selenium()
    i = 0
    for link in links:
        try:
            print(f"[{i}/{len(links)}] Processing: {link} - {links[link]}")
            
            file_path = download_file_from_page(
                page_url=links[link],
                file_name=link
            )
            
            if file_path:
                downloaded_files.add(file_path)
                print(f"  ✓ Downloaded: {os.path.basename(file_path)}")
            else:
                print(f"  ⚠ No download button found")
            
            # Рандомизированная задержка между страницами
            if i < len(links):  # Не ждать после последней страницы
                apply_delay(min_delay, max_delay)
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"  ⚠ Rate limited (429). Pausing for 10s...")
                time.sleep(10)
            else:
                print(f"  ✗ HTTP error {e.response.status_code}: {e}")
        i+=1
    
    return downloaded_files


def validate_url(url: str) -> bool:
    """
    Проверяет корректность URL.
    
    :param url: URL для проверки
    :returns: True если URL корректный, иначе False
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def clean_numeric(value: str) -> Optional[float]:
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
        return num / 100 if is_percent else num
    except ValueError:
        return None


def extract_ticker_from_filename(filename: str) -> str:
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
    years = [str(cell).strip() for cell in df_raw.iloc[year_row_idx, 1:] if pd.notna(cell) and cell != '']
    
    if not years:
        return pd.DataFrame()
    
    # Собираем данные
    records = []
    ticker = extract_ticker_from_filename(file_path.name)
    
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
                continue
            
            numeric_value = clean_numeric(raw_value)
            if numeric_value is not None or raw_value.strip():
                records.append({
                    'ticker': ticker,
                    'filename': file_path.name,
                    'indicator': indicator,
                    'year': year,
                    'value': numeric_value if numeric_value is not None else raw_value.strip()
                })
    
    return pd.DataFrame(records)


def merge_files(directory: str, pattern: str = '*.csv') -> pd.DataFrame:
    """
    Объединяет все CSV файлы из директории в единый DataFrame.
    
    :param directory: Путь к директории с CSV файлами
    :param pattern: Шаблон поиска файлов (по умолчанию '*.csv')
    :returns: Объединённый DataFrame с колонками:
              [ticker, filename, indicator, year, value]
    :raises ValueError: При ошибках обработки
    """
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError(f"Директория не найдена: {directory}")
    
    csv_files = list(dir_path.glob(pattern))
    if not csv_files:
        raise ValueError(f"Не найдено CSV файлов по шаблону '{pattern}' в {directory}")
    
    print(f"Найдено файлов: {len(csv_files)}")
    
    all_data = []
    
    for file_path in sorted(csv_files):
        try:
            df = parse_financial_csv(file_path)
            if not df.empty:
                all_data.append(df)
                print(f"✓ {file_path.name:20s} → {len(df)} записей")
            else:
                print(f"⚠ {file_path.name:20s} → пустой")
        except Exception as e:
            print(f"✗ {file_path.name:20s} → ошибка: {e}")
            continue
    
    if not all_data:
        return pd.DataFrame(columns=['ticker', 'filename', 'indicator', 'year', 'value'])
    
    merged_df = pd.concat(all_data, ignore_index=True)
    
    # Преобразуем числовые значения где возможно
    merged_df['value_numeric'] = pd.to_numeric(merged_df['value'], errors='coerce')
    
    print(f"\n✅ Объединено: {len(merged_df)} записей из {len(all_data)} файлов")
    print(f"   Уникальных тикеров: {merged_df['ticker'].nunique()}")
    print(f"   Уникальных показателей: {merged_df['indicator'].nunique()}")
    print(f"   Годы: {sorted(merged_df['year'].unique())}")
    
    return merged_df


def pivot_financial_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Преобразует длинный формат данных в широкий (показатели как строки, годы как столбцы).
    
    :param df: DataFrame из merge_financial_files()
    :returns: Сводная таблица с колонками [ticker, filename, indicator, 2008, 2009, ...]
    """
    if df.empty:
        return pd.DataFrame()
    
    # Используем числовые значения где есть, иначе оригинальные
    df_pivot = df.pivot_table(
        index=['ticker', 'filename', 'indicator'],
        columns='year',
        values='value_numeric',
        aggfunc='first'
    ).reset_index()
    
    # Сортируем годы
    year_cols = sorted([col for col in df_pivot.columns if col not in ['ticker', 'filename', 'indicator']], 
                      key=lambda x: int(x) if x.isdigit() else 9999)
    
    # Формируем итоговый порядок колонок
    cols_order = ['ticker', 'filename', 'indicator'] + year_cols
    df_pivot = df_pivot[cols_order]
    
    return df_pivot

if __name__=='__main__':
    scrape_and_download()
    # print(download_file_from_page(page_url='https://smart-lab.ru/q/VTBR/f/y/'))