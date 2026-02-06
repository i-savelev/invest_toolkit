# контекст для проекта invrst_toolkit

## описание проекта
Сейчас проект состоит из трех частей
1. moex_broker_toolkit - модули для обработки брокерских отчётов
2. fin_analysis - модули для анализа акций
3. sl_scrapper - модуль для парсинга данных с сайта smart-lab.ru (scrapper_reports в папке support_files)
в папке support_files хранятся файлы с таблицами и другими данными

## Основные задачи по проекту
1. Упростить сложные модули в moex_broker_toolkit. там слишком много ООП, наследования и т.д. Привести все к простым модулям, которые обмениваются простыми и понятными данными.
2. Реорганизовать проект. Вот образец желаемой структуры

invest_toolkit/
├── data/                  # Только данные, без логики
│   ├── __init__.py
│   ├── portfolio.py       # PortfolioPosition, RebalancingPlan (dataclass)
│   └── company.py         # CompanyData (dataclass)
├── io/                    # Ввод/вывод (побочные эффекты)
│   ├── __init__.py
│   ├── brokers.py         # parse_vtb(), parse_sber(), load_distribution()
│   ├── moex.py            # get_price(ticker) — простая функция
│   └── smartlab.py        # scrape_reports()
├── core/                  # Чистая бизнес-логика (без побочных эффектов!)
│   ├── __init__.py
│   ├── scoring.py         # calculate_growth_score(series, periods)
│   ├── rebalancing.py     # calculate_target_weights(), adjust_for_budget()
│   └── allocation.py      # distribute_funds(portfolio, target, deposit)
├── viz/                   # Визуализация
│   ├── __init__.py
│   └── charts.py          # plot_portfolio(), plot_company_metrics()
├── reports/               # Генерация отчётов
│   ├── __init__.py
│   └── markdown.py        # generate_markdown_report(plan, template_path)
└── main.py                # Оркестрация: только вызов функций из модулей

3. Интегрировать логику парсинга и обогащения данных из модулей `sber_parser.py`, `broker_parser.py`, `report_registry.py` и `all_stock_info.py` в новые функциональные модули в `src_invest_toolkit`.

**Я создал папку src_invest_toolkit. в ней есть все необходимые папки. Если не получается создать папку, проси сделать это меня. Давай новые модуля размещать там. При этом старые не удалять**

## Что нужно учитывать?
1. Логгирование. В код необходимо добавлять логирование с помощью модуля logger из корня проекта. логгирование должно быть подробным и понятным.

## требования к коду
1. Стиль кода:
   - Следуешь PEP 8.
   - Используешь snake_case для методов и переменных.
   - Используешь PascalCase для классов.
   - Все методы — с аннотацией типов (type hints).
2. Структура методов:
   - Каждый метод решает одну задачу (принцип единственной ответственности).
   - Методы короткие и читаемые.
   - Избегай side effects, когда это возможно
3. Документирование (docstring):
   - Используй многострочные docstrings в формате reStructuredText.
   - Пример оформления:

        def add(a: int, b: int) -> int:
        	 """Складывает два целых числа.
             :param a: Первое слагаемое
             :param b: Второе слагаемое
             :returns: Сумма a и b.
        	 """
        	 return a + b
4. Примеры использования (опционально):
   - Если уместно, добавляй раздел Example: в docstring.
 
## Контекст
Можешь дополнять этот файл важными деталями для улучшения контекста.
Добавляй заголовки и записывай важную информацию в конец файла.

## Текущий статус
Начата работа по реорганизации проекта. Новые модули создаются в папке `src_invest_toolkit`.


1. Успешно выполнен рефакторинг модуля `moex_broker_toolkit/sber_splitter.py`.
   - Новые функции `split_sber_report` и `save_tables_to_excel` размещены в `src_invest_toolkit/io/brokers.py`.

2. Успешно интегрирована логика из `sber_parser.py`, `broker_parser.py`, `all_stock_info.py`.
   - Создан модуль `src_invest_toolkit/core/sber.py` с функцией `calculate_sber_balance_report` для полной обработки отчёта.
   - Создан модуль `src_invest_toolkit/io/moex.py` для загрузки справочной информации и цен с MOEX.
   - Создан модуль `src_invest_toolkit/core/portfolio.py` для работы с данными портфеля (dataclasses и бизнес-логика).

Добавлены файлы `__init__.py` в `src_invest_toolkit`, `src_invest_toolkit/io` и `src_invest_toolkit/core`.

Обнаруженные и устраненные ошибки:
- Решена проблема с зависимостью `html5lib` путем обновления `pandas[excel,html]` в `pyproject.toml`.
- Добавлена логика в функцию `save_tables_to_excel` для автоматического создания выходной директории.


Старые модули остаются без изменений для обратной совместимости.