# invest_toolkit

<img width="2088" height="1166" alt="изображение" src="https://github.com/user-attachments/assets/8ac44afb-0cbb-49f7-a754-079145ee814a" />


Инструментарий для анализа инвестиционного портфеля, расчёта рейтингов и визуализации данных по акциям MOEX.

---

## Возможности

- Парсинг отчётов брокеров (Сбербанк, ВТБ)
- Загрузка данных с MOEX API и SmartLab
- Расчёт целевого распределения портфеля и ребалансировка
- Построение графиков с скользящей средней
- Автоматический расчёт инвестиционного рейтинга
- Генерация отчётов в Markdown
- Все функции возвращают `pd.DataFrame` и автоматически логируются в `.log/app.log`

---

## Установка

```bash
# Через uv (рекомендуется)
uv pip install -e .

# Или через pip
pip install -e .
```

> Требуется Python ≥3.13

---

## 📦 Быстрый старт и примеры использования

### Получение финансовых данных с smartlab

```python
import invest_toolkit as it

it.scrape_and_download(
  save_directory= r'support_files/scrapper_reports'
)
```
Данные по финансовым показателям каждоый компании с сайта smartlab в формате csv будут сохранены в указанную папку

### Сбор всех данных по акциям (moex api + отчеты с smartlab)
```python
import invest_toolkit as it

df = it.all_stock_info(
    free_dloat_path='support_files/20251206-free-float.xlsx',
    ir_path='support_files/ir_rating.xlsx',
    sl_stock_folder='support_files/scrapper_reports',
)
```
Будет создан датафрейм следующего вида

```
ТАБЛИЦА: Результат выполнения 'all_stock_info'
Размер: 149726 строк × 5 столбцов
================================================================================
   ticker indicator       value  type year
0    SBER      name    Сбербанк  moex  NaN
1    ROSN      name    Роснефть  moex  NaN
2    NVTK      name  Новатэк ао  moex  NaN
3    LKOH      name      ЛУКОЙЛ  moex  NaN
4    PLZL      name       Полюс  moex  NaN
5    GAZP      name  ГАЗПРОМ ао  moex  NaN
6    SIBN      name  Газпрнефть  moex  NaN
7    GMKN      name   ГМКНорНик  moex  NaN
8    YDEX      name      ЯНДЕКС  moex  NaN
9    TATN      name  Татнфт 3ао  moex  NaN
10   OZON      name        Озон  moex  NaN
11      T      name  Т-Техно ао  moex  NaN
12   PHOR      name  ФосАгро ао  moex  NaN
```

### Визуализация

```python
import invest_toolkit as it
# Один график
it.plot_one_chart(
    df=df,
    ticker='SBER',
    title='Чистая прибыль, млрд руб',
    window=3  # окно скользящей средней
)

# Несколько графиков
it.plot_multiple_chart(
    df=df,
    ticker='SBER',
    metric_list=['Чистая прибыль, млрд руб', 'Див.выплата, млрд руб'],
    rows=2, cols=1
)
```
Примеры графиков

<img width="600" height="500" alt="изображение" src="https://github.com/user-attachments/assets/fcb99a0d-c69f-4383-8396-f53373b951bf" />


### Рейтинг

```python
import invest_toolkit as it
# Расчёт рейтинга
rating = it.rating_df(df, n=7) # (df = it.all_stock_info)
```
Пример расчета рейтинга
```
ТАБЛИЦА: Результат выполнения 'rating_df'
Размер: 2331 строк × 5 столбцов
================================================================================
   ticker           type              indicator  year                                            value
0    ABIO         rating                     IR  None                                             0.77
1    ABIO         rating          Выплата див-в  None                                             0.29
2    ABIO  rating_string  Выплата див-в, расчет  None       Кол-во [Див.выплата, млрд руб]: 2/7 = 0.29
3    ABIO         rating             Рост див-в  None                                             0.29
4    ABIO  rating_string     Рост див-в, расчет  None         Рост [Див.выплата, млрд руб]: 2/7 = 0.29
5    ABIO         rating           Рост прибыли  None                                             0.43
6    ABIO  rating_string   Рост прибыли, расчет  None      Рост [Чистая прибыль, млрд руб]: 3/7 = 0.43
```

🔗 **[Рейтинг на datalens](https://datalens.yandex/5ylyszbllnt6p)**

### Управление портфелем

```python
it.portfolio_report(
    report_path_sber='.reports/sber_27012026.html',
    report_path_vtb='.reports/vtb20260208.xlsx',
    allocation_path='support_files/index_fund.xlsx',
    deposit=100000,
    grouping_tickers=['LQDT', 'SBMM'],
    allow_sell_tickers=['LQDT', 'SBMM'],
    sell=True,
    report_save_path='.output'
)
```
Пример отчета по портфелю
 
```

Общая сумма активов = 2310810 руб.

Акции = 1291352.0 руб. (55.9/60.0%)

Денежный рынок = 1019458.0 руб. (44.1/40.0%)

Пополнение = 100000

## Исходный отчет
        

| ticker     | buy/sell                     | %_src | %_tgt | %_res |
| :--------- | :--------------------------- | ----: | ----: | ----: |
| AQUA       | buy 11 шт. (5380 руб.)       |  0.72 |  0.96 |  0.91 |
| BSPB       | buy 2 шт. (6843 руб.)        |  1.63 |  1.93 |  1.85 |
| CHMF       | -                            |  0.67 |   0.6 |  0.64 |
| HEAD       | buy 5 шт. (14560 руб.)       |  1.51 |  2.27 |  2.05 |
| IRAO       | buy 29 шт. (9599 руб.)       |  2.48 |  2.84 |  2.77 |
| LKOH       | -                            |  4.95 |   4.2 |  4.74 |
| LSNGP      | -                            |  1.75 |  1.57 |  1.68 |
| ...        | ...                          |   ... |   ... |   ... |
| SNGSP      | -                            |  0.77 |   0.6 |  0.74 |
| T          | buy 6 шт. (21037 руб.)       |  2.73 |  3.73 |  3.49 |
| TATN       | -                            |  2.42 |   1.8 |  2.32 |
| TRNFP      | -                            |  3.25 |     3 |  3.12 |
| WTCMP      | buy 2 шт. (2584 руб.)        |  1.01 |  1.09 |  1.07 |
| X5         | buy 5 шт. (12132 руб.)       |  2.73 |  3.19 |  3.12 |
| YDEX       | -                            |   2.7 |  2.48 |  2.59 |
| LQDT, SBMM | sell 27910 шт. (-55131 руб.) | 44.12 |    40 |    40 |

AQUA: buy 11 шт. (5380 руб.)
BSPB: buy 2 шт. (6843 руб.)
HEAD: buy 5 шт. (14560 руб.)
...
WTCMP: buy 2 шт. (2584 руб.)
X5: buy 5 шт. (12132 руб.)
LQDT, SBMM: sell 27910 шт. (-55131 руб.)
```


Полные рабочие примеры использования находятся в Jupyter-ноутбуках в папке [`notebooks/`](notebooks/):

- `analysis.ipynb` — анализ данных и рейтинги
- `portfolio.ipynb` — управление портфелем и ребалансировка
- `data.ipynb` — загрузка и предобработка данных
---

## Структура

```
invest_toolkit/
├── notebooks/          # Jupyter-ноутбуки с примерами ← начните отсюда
├── src/invest_toolkit/
│   ├── core/           # Бизнес-логика (портфель, рейтинги)
│   ├── io/             # Загрузка данных (брокеры, MOEX, SmartLab)
│   ├── orchestration/  # Основные workflows
│   ├── reports/        # Генерация Markdown-отчётов
│   ├── utils/          # Логирование и декораторы
│   └── viz/            # Визуализация (matplotlib)
├── support_files/      # Конфигурационные Excel-файлы
└── pyproject.toml
```
---

## ⚙️ Конфигурация

Целевое распределение настраивается в `support_files/index_fund.xlsx`:
- Лист `categories` — доли категорий (акции, ETF)
- Отдельные листы — тикеры и веса внутри категорий

---

## 📝 Логирование

```python
from invest_toolkit.utils import log

log.init("my_script.py")  # инициализация
log.info("Сообщение")      # запись в .log/app.log
```

Все `DataFrame`, возвращаемые функциями, автоматически логируются в табличном виде.


---

> 📌 **Совет**: Для работы скрапера SmartLab требуется Firefox и `geckodriver`. Все пути в примерах относительные — адаптируйте под свою структуру проекта.
