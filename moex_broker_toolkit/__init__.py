"""
Модуль `moex_broker_toolkit` — система для анализа и ребалансировки инвестиционного портфеля.

Содержит компоненты для:
- парсинга отчётов брокеров (ВТБ, Сбер),
- загрузки справочников,
- расчёта целевого распределения,
- генерации рекомендаций и отчётов.

Основные компоненты:

**Источники данных**
- `AllStockInfo` — справочник инструментов (ISIN, тикеры, лоты).
- `TableSplitter`, `VtbSplitter`, `SberSplitter` — разделение отчётов на таблицы.
- `BrokerParser`, `VtbParser`, `SberParser` — извлечение позиций из таблиц.

**Анализ и расчёт**
- `ReportRegistry` — агрегация отчётов.
- `BalanceReport` — объединение брокерских отчётов и расчёта стоимости.
- `DistributionTable` — целевое распределение (план).
- `TargetAllocator` — расчёт операций (покупка/продажа) под бюджет.

**Генерация отчётов**
- `ReportStrategy` (ABC) — абстрактная стратегия форматирования.
- `MdReportStrategy` — реализация для Markdown.
- `ReportGenerator` — управление стратегиями и сохранением.

**Внешние зависимости**
- `moex_api_utils` — API для получения цен с MOEX (не класс, а модуль утилит).
"""

from .all_stock_info import AllStockInfo
from .balance_report import BalanceReport
from .broker_parser import BrokerParser
from .distribution_table import DistributionTable
from .md_report_strategy import MdReportStrategy
from fin_analysis.utils import moex_api_utils
from .report_generator import ReportGenerator
from .report_registry import ReportRegistry
from .report_strategy import ReportStrategy
from .sber_parser import SberParser
from .sber_splitter import SberSplitter
from .table_splitter import TableSplitter
from .target_allocator import TargetAllocator
from .vtb_parser import VtbParser
from .vtb_splitter import VtbSplitter