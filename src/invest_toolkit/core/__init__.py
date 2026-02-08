"""
Пакет для чистой бизнес-логики.

Содержит модули, содержащие функции без побочных эффектов.
"""
from .portfolio import summary_report
from .target_allocation import allocation_report, group_by_category, allow_sell, adjust_for_deposit