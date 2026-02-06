"""
Пакет для операций ввода-вывода (I/O).

Содержит модули для работы с внешними источниками данных:
- brokers.py: парсинг брокерских отчётов (Сбербанк, ВТБ и др.)
- moex.py: загрузка данных с Московской биржи
- smartlab.py: парсинг данных с сайта smart-lab.ru
"""

# Импортируем основные функции в пространство имён пакета для удобства
from .brokers import split_sber_report, save_tables_to_excel
from .moex import all_instruments_info, get_price