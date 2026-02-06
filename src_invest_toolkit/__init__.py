"""
Основной пакет инвестиционного инструментария.

Этот модуль инициализирует пакет `src_invest_toolkit` и настраивает путь для корректного импорта
модулей, расположенных в корне проекта (например, `logger`).
"""

import sys
import os

# Добавляем корень проекта в sys.path, чтобы можно было импортировать модули на уровне проекта
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)