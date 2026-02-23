"""
Основной пакет инвестиционного инструментария.

Этот модуль инициализирует пакет `src_invest_toolkit` и настраивает путь для корректного импорта
модулей, расположенных в корне проекта (например, `logger`).

Устанвока
uv pip install -e .
"""
from .orchestration import *
from .io import merge_csv_files, free_float, all_instruments_info, ir_rating, scrape_and_download
from .utils import log
from .viz import plot_one_chart, plot_multiple_chart
