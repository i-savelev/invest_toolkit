# 📊 `moex_broker_toolkit` — Автоматизированный анализ брокерских отчётов и ребалансировка портфеля

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Цель**: Упростить агрегацию позиций из нескольких брокеров (ВТБ, Сбер), расчёт рыночной стоимости портфеля, сравнение с целевым распределением и формирование рекомендаций по покупке/продаже ценных бумаг — с учётом бюджета, лотов и ограничений.

---

## 🌟 Возможности

- ✅ **Парсинг отчётов**:
  - ВТБ (`.xlsx`, «Отчёт об остатках ценных бумаг»)
  - Сбербанк (`.html`, `pandas.read_html`)
- ✅ **Агрегация портфеля** из нескольких источников
- ✅ **Получение актуальных цен** через [MOEX ISS API](https://iss.moex.com)
- ✅ **Задание целевого распределения** через Excel-шаблон (`categories` + листы на категорию)
- ✅ **Расчёт операций** (`buy`/`sell`) с учётом:
  - размера лота,
  - доступного бюджета (`deposit`),
  - разрешения на продажи (`allow_sell`, `tickers_to_sell`),
  - округления до целых лотов.
- ✅ **Генерация отчётов**:
  - Markdown (с шаблонами),
  - Excel (промежуточные и финальные таблицы),
  - расширяемо через паттерн **Strategy**.

---

## 📦 Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/moex_broker_toolkit.git
cd moex_broker_toolkit

# Установите зависимости
pip install pandas openpyxl requests tabulate
# (опционально) для асинхронного API: aiohttp
```

> 💡 Минимальные требования: Python ≥ 3.9, `pandas`, `openpyxl` (для Excel), `requests` (для MOEX API), `tabulate` (для `.to_markdown()`).

---

## 🧩 Архитектура

| Модуль                                         | Назначение                                                 |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `all_stock_info.py`                            | Загрузка справочника (ISIN → SECID, LOTSIZE, SHORTNAME)    |
| `table_splitter.py` / `*.splitter.py`          | Разделение отчётов на логические таблицы                   |
| `broker_parser.py` / `*.parser.py`             | Извлечение позиций (ISIN, количество) и обогащение данными |
| `report_registry.py`                           | Агрегация отчётов от разных брокеров                       |
| `balance_report.py`                            | Объединение + расчёт стоимости/долей                       |
| `distribution_table.py`                        | Загрузка и валидация целевого распределения                |
| `target_allocator.py`                          | Расчёт `buy`/`sell` с бюджетным ограничением               |
| `report_strategy.py` / `md_report_strategy.py` | Генерация отчётов (поддержка шаблонов)                     |
| `report_generator.py`                          | Управление стратегиями (`Strategy` pattern)                |
| `moex_api_utils.py`                            | Получение цен с MOEX (`LAST`, `MARKETPRICE`)               |

---

## 🚀 Быстрый старт

### 1. Подготовьте данные

- `support_files/rates_all.csv` — справочник ЦБ (см. `AllStockInfo.get_all_stock_df` — 3 строки служебных, 3-я — заголовки).
- `support_files/index_fund.xlsx` — шаблон распределения:
  - лист `categories`: `category`, `%`
  - листы `stock`, `bonds`, …: `ticker`, `%`
  - *Сумма `%` на каждом листе = 100%*
- Отчёты брокеров:
  - ВТБ: Excel, лист `brokerage_report`
  - Сбер: HTML (сохранённый из ЛК)

### 2. Запустите скрипт

```python
import moex_broker_toolkit as mbtk
import datetime

if __name__ == "__main__":
    date = datetime.date.today()

    # 1. Загрузите справочник
    all_stock = mbtk.AllStockInfo(path=r'support_files/rates_all.csv')

    # 2. Разделите отчёты
    splitter_vtb = mbtk.VtbSplitter()
    splitter_vtb.split(r'.reports/vtb20251026_20251125.xlsx')

    splitter_sber = mbtk.SberSplitter()
    splitter_sber.split(r'.reports/sber_14112025.html')

    # 3. Зарегистрируйте
    registry = mbtk.ReportRegistry()

    # 4. Распарсьте и агрегируйте
    vtb = mbtk.VtbParser(all_stock, splitter_vtb, registry)
    sber = mbtk.SberParser(all_stock, splitter_sber, registry)

    vtb.get_balance_report_df()
    sber.get_balance_report_df()

    # 5. Целевое распределение
    dist_table = mbtk.DistributionTable(r'support_files/index_fund.xlsx', all_stock)
    dist_table.get_table().to_excel(f'.output/dt_{date}.xlsx', index=False)

    # 6. Итоговый портфель
    bal_report = mbtk.BalanceReport(registry, dist_table)
    bal_report.get_balance_report().to_excel(f'.output/br_{date}.xlsx', index=False)

    # 7. Расчёт операций
    allocator = mbtk.TargetAllocator(
        balance_report=bal_report,
        distribution_table=dist_table,
        deposit=40_000,
        allow_sell=False,
        tickers_to_sell=['SBMM', 'LQDT']
    )
    alloc_df = allocator.get_distrib_of_money_df()
    alloc_df.to_excel(f'.output/TargetAllocator_{date}.xlsx', index=False)

    # 8. Генерация отчёта
    strategy = mbtk.MdReportStrategy(allocator, r'templates/md_template.md')
    generator = mbtk.ReportGenerator(strategy)
    generator.generate_report()
    generator.save_report(f'./broker_report_{date}.md')
```

---

## 📄 Пример шаблона Markdown (`md_template.md`)

```markdown
# 📈 Отчёт по портфелю на {date}

- Общая стоимость: {all_money_sum:,} ₽  
- Депозит: {deposit:,} ₽  
- Акции: {stock_percent}% ({stock_sum:,} ₽), цель: {stock_target}%  
- Облигации: {bonds_percent}% ({bonds_sum:,} ₽), цель: {bonds_target}%

## 📋 Рекомендуемые операции

{distribution_table}

### 💬 Кратко:

{distribution_string}
```

Результат генерации будет содержать таблицу вида:

| ticker | buy/sell           | %_source | %_target | %_calc |
| ------ | ------------------ | -------- | -------- | ------ |
| SBER   | buy 2 шт. (600 ₽)  | 10.2     | 15.0     | 12.5   |
| GAZP   | sell 1 шт. (150 ₽) | 8.7      | 5.0      | 6.1    |

---

## 🛠️ Кастомизация

### Добавить нового брокера

1. Создайте `MyBrokerSplitter(TableSplitter)` → реализуйте `split()`.
2. Создайте `MyBrokerParser(BrokerParser)` → реализуйте `get_source_df()`.
3. Зарегистрируйте в `ReportRegistry`.

### Добавить формат отчёта

Реализуйте новую стратегию:

```python
class HtmlReportStrategy(mbtk.ReportStrategy):
    def generate(self) -> str:
        # ...
        return "<html>...</html>"
```

Передайте в `ReportGenerator`.

---

## ⚠️ Важные замечания

- **ISIN → SECID**: Парсеры ожидают, что в отчёте есть ISIN, а в справочнике — соответствие `ISIN → SECID`.  
  Убедитесь, что `rates_all.csv` содержит оба поля.
- **MOEX API**:  
  - Используется `https://iss.moex.com/iss/engines/stock/markets/shares/securities/{ticker}.json`
  - При частых вызовах может потребоваться кэширование или `time.sleep(0.1)`.
- **Лоты**: Все операции округляются до целых лотов (`floor` для покупок, `ceil` для продаж).
- **Ошибки валидации**:
  - `100%` не выполнено → `ValueError`
  - Тикер не найден → `IndexError`
  - Нет данных в MOEX → `RuntimeError`

---

## 📁 Структура проекта

```
moex_broker_toolkit/
├── __init__.py                 # Публичный API
├── all_stock_info.py
├── balance_report.py
├── broker_parser.py
├── distribution_table.py
├── md_report_strategy.py
├── report_generator.py
├── report_registry.py
├── report_strategy.py
├── sber_parser.py
├── sber_splitter.py
├── table_splitter.py
├── target_allocator.py
├── vtb_parser.py
└── vtb_splitter.py


fin_analysis
└── utils/
    └── moex_api_utils.py

support_files/                  # Ваши данные
├── rates_all.csv
└── index_fund.xlsx

templates/
└── md_template.md

.output/                        # Выходные файлы (создаётся автоматически)
```



