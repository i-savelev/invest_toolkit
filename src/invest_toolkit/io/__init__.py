"""
Пакет для операций ввода-вывода (I/O).

Содержит модули для работы с внешними источниками данных:
- brokers.py: парсинг брокерских отчётов (Сбербанк, ВТБ и др.)
- moex.py: загрузка данных с Московской биржи
- smartlab.py: парсинг данных с сайта smart-lab.ru
"""

# Импортируем основные функции в пространство имён пакета для удобства
from .brokers import read_vtb, read_sber
from .moex import all_instruments_info
from .allocation import allocatin_table
from.sl_scrapper import scrape_and_download
from .stocks import merge_csv_files, free_float, ir_rating