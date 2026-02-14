import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Set, Optional, Dict
import os
import time
import random
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict
import time
from invest_toolkit.utils import log


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
}

def _get_tickers_with_selenium() -> Dict[str, str]:
    """
    Извлекает тикеры через рендеринг JavaScript с помощью Selenium.
    
    :returns: Словарь {тикер: ссылка}
    :raises Exception: При ошибках драйвера или таймауте
    """
    log.info("Starting Selenium scraping...")
    options = Options()
    # Отключаем детект автоматизации
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    
    driver = webdriver.Firefox(options=options)
    
    try:
        driver.get('https://smart-lab.ru/q/shares/')
        
        # Ждём загрузки таблицы по появлению ячеек с тикерами
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.trades-table__ticker'))
        )
        
        # Дополнительная пауза для полной загрузки данных
        time.sleep(3)
        
        ticker_links = {}
        
        # Извлекаем все ячейки с тикерами
        ticker_cells = driver.find_elements(By.CSS_SELECTOR, '.trades-table__ticker')
        
        for cell in ticker_cells:
            try:
                # Получаем тикер из текста ячейки
                ticker_text = cell.text.strip()
                if not ticker_text:
                    continue
                
                # Находим родительскую строку таблицы
                row = cell.find_element(By.XPATH, './ancestor::tr')
                
                # Ищем ссылку на фундаментальный анализ в строке
                try:
                    link_element = row.find_element(By.CSS_SELECTOR, 'a.charticon2')
                    href = link_element.get_attribute('href')
                    if href:
                        ticker_links[ticker_text] = href
                except:
                    continue
                    
            except Exception as e:
                print(f"⚠ Ошибка при обработке ячейки: {e}")
                continue
        
        print(f"✅ Получено {len(ticker_links)} тикеров через Selenium")
        log.info(f"✅ Получено {len(ticker_links)} тикеров через Selenium")
        return ticker_links
    
    finally:
        driver.quit()


def _download_file_from_page(
        page_url: str, 
        save_directory: str,
        download_selector: str = 'a.download-table',
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


def _get_random_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> float:
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


def _apply_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> None:
    """
    Выполняет задержку с рандомизацией для вежливого скрапинга.
    
    :param min_delay: Минимальная задержка в секундах
    :param max_delay: Максимальная задержка в секундах
    """
    delay = _get_random_delay(min_delay, max_delay)
    time.sleep(delay)


def scrape_and_download(
        save_directory:str,
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
    links = _get_tickers_with_selenium()
    i = 0
    for link in links:
        try:
            print(f"[{i}/{len(links)}] Processing: {link} - {links[link]}")
            log.info(f"[{i}/{len(links)}] Processing: {link} - {links[link]}")
            
            file_path = _download_file_from_page(
                save_directory=save_directory,
                page_url=links[link],
                file_name=link
            )
            
            if file_path:
                downloaded_files.add(file_path)
                print(f"  ✓ Downloaded: {os.path.basename(file_path)}")
                log.info(f"  ✓ Downloaded: {os.path.basename(file_path)}")
            else:
                print(f"  ⚠ No download button found")
                log.info(f"  ⚠ No download button found")
            
            # Рандомизированная задержка между страницами
            if i < len(links):  # Не ждать после последней страницы
                _apply_delay(min_delay, max_delay)
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"  ⚠ Rate limited (429). Pausing for 10s...")
                log.error(f"  ⚠ Rate limited (429). Pausing for 10s...")
                time.sleep(10)
            else:
                print(f"  ✗ HTTP error {e.response.status_code}: {e}")
                log.error(f"  ✗ HTTP error {e.response.status_code}: {e}")
        i+=1
    
    return downloaded_files



if __name__=='__main__':
    scrape_and_download(
        save_directory= r'./.output/test_scrapper'
    )
    # print(download_file_from_page(page_url='https://smart-lab.ru/q/VTBR/f/y/'))