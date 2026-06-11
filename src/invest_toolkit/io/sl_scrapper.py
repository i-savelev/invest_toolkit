import random
import re
import time
from io import StringIO
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

import pandas as pd
import requests
from bs4 import BeautifulSoup

from invest_toolkit.utils import log


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

YEAR_PATTERN = re.compile(r"^\d{4}$")
SHARE_TICKER_PATTERN = re.compile(r"^[A-Z0-9]+P?$")
LTM_COLUMN = "LTM"
INDICATOR_COLUMN = "__indicator__"
SMARTLAB_YEARLY_REPORT_URL = "https://smart-lab.ru/q/{ticker}/f/y/"
SMARTLAB_SHARES_URL = "https://smart-lab.ru/q/shares/"

INDICATOR_ALIASES = {
    "оперденежныйпотокмлрдруб": "операционныйденежныйпотокмлрдруб",
    "произвтрудамлнрубчелгод": "производительностьтрудамлнрубчелгод",
    "произвтрудамлнрубчелвгод": "производительностьтрудамлнрубчелгод",
    "расходычелгодтыср": "расходычелгодтыср",
}


def _normalize_text(value: object) -> str:
    """
    Приводит текст к единому строковому виду без лишних пробелов.

    :param value: Исходное значение ячейки или заголовка.
    :returns: Очищенная строка.
    """
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").replace("\ufeff", "").strip()
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([,.;:])", r"\1", text)


def _normalize_header_value(value: object) -> str:
    """
    Нормализует заголовок таблицы, включая многоуровневые tuple-колонки pandas.

    :param value: Исходное значение заголовка.
    :returns: Плоское строковое представление заголовка.
    """
    if isinstance(value, tuple):
        parts = [_normalize_text(part) for part in value if _normalize_text(part)]
        return " ".join(parts)
    return _normalize_text(value)


def _normalize_indicator_for_match(indicator: str) -> str:
    """
    Нормализует название показателя для сопоставления с локальным CSV.

    :param indicator: Название показателя из HTML-таблицы или CSV.
    :returns: Нормализованная строка для сравнения.
    """
    normalized = _normalize_text(indicator).lower().replace("ё", "е")
    replacements = {
        "произв.": "производительность",
        "произв": "производительность",
        "опер.денежный": "операционный денежный",
        "операц": "операционный",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)

    normalized = re.sub(r"[^a-zа-я0-9]+", "", normalized)
    return INDICATOR_ALIASES.get(normalized, normalized)


def _normalize_ticker(value: str) -> str:
    """
    Нормализует тикер для внутренних сравнений.

    :param value: Исходный тикер.
    :returns: Тикер в верхнем регистре без лишних пробелов.
    """
    return _normalize_text(value).upper()


def _is_year_column(column_name: str) -> bool:
    """
    Проверяет, является ли имя столбца годом.

    :param column_name: Имя столбца.
    :returns: ``True``, если столбец содержит год в формате YYYY.
    """
    return bool(YEAR_PATTERN.fullmatch(_normalize_text(column_name)))


def _is_ltm_column(column_name: str) -> bool:
    """
    Проверяет, соответствует ли имя столбца периоду LTM.

    SmartLab иногда добавляет к заголовку `LTM` служебный символ `?` из tooltip,
    поэтому проверка не должна опираться только на точное совпадение строки.

    :param column_name: Имя столбца или текст ячейки.
    :returns: ``True``, если столбец соответствует LTM.
    """
    normalized = _normalize_text(column_name).upper()
    return normalized == LTM_COLUMN or normalized.startswith(f"{LTM_COLUMN} ")


def _normalize_period_name(period_name: str) -> str:
    """
    Нормализует имя периода к каноническому виду.

    :param period_name: Имя периода, переданное пользователем или прочитанное из HTML.
    :returns: Каноническое имя периода.
    :raises ValueError: Если имя периода пустое или не поддерживается.
    """
    normalized = _normalize_text(period_name).upper()
    if not normalized:
        raise ValueError("Список периодов содержит пустое значение.")
    if _is_year_column(normalized):
        return normalized
    if _is_ltm_column(normalized):
        return LTM_COLUMN
    raise ValueError(f"Неподдерживаемый период SmartLab: {period_name}")


def _get_random_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> float:
    """
    Генерирует случайную задержку в указанном диапазоне.

    :param min_delay: Минимальная задержка в секундах.
    :param max_delay: Максимальная задержка в секундах.
    :returns: Случайное значение задержки.
    """
    if min_delay < 0 or max_delay < 0:
        raise ValueError("Delays must be non-negative")
    if min_delay > max_delay:
        raise ValueError("min_delay cannot be greater than max_delay")
    return random.uniform(min_delay, max_delay)


def _apply_delay(min_delay: float = 1.5, max_delay: float = 4.0) -> None:
    """
    Выполняет паузу между запросами к SmartLab.

    :param min_delay: Минимальная задержка в секундах.
    :param max_delay: Максимальная задержка в секундах.
    """
    time.sleep(_get_random_delay(min_delay, max_delay))


def _get_existing_report_paths(save_directory: str) -> Dict[str, Path]:
    """
    Находит все уже сохранённые CSV-отчёты в целевой папке.

    :param save_directory: Путь к директории с локальными CSV SmartLab.
    :returns: Словарь вида ``{ticker: path_to_csv}``.
    :raises ValueError: Если директория не существует.
    """
    directory = Path(save_directory)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Директория не найдена: {save_directory}")

    csv_paths = sorted(directory.glob("*.csv"))
    reports = {_normalize_ticker(path.stem): path for path in csv_paths}
    log.info(f"Найдено локальных отчётов SmartLab: {len(reports)}")
    return reports


def _fetch_share_tickers(timeout: int = 30) -> list[str]:
    """
    Загружает список тикеров акций со страницы SmartLab ``/q/shares/``.

    :param timeout: Таймаут HTTP-запроса в секундах.
    :returns: Упорядоченный список тикеров без дублей.
    :raises ValueError: Если на странице не удалось найти таблицу с тикерами.
    """
    html = _fetch_company_page(page_url=SMARTLAB_SHARES_URL, timeout=timeout)
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        ticker_idx = None
        data_rows = []
        for row in rows:
            header_cells = row.find_all(["th", "td"])
            headers = [_normalize_text(cell.get_text(" ", strip=True)) for cell in header_cells]
            if "Тикер" in headers:
                ticker_idx = headers.index("Тикер")
                continue

            if ticker_idx is not None:
                data_rows.append(row)

        if ticker_idx is None:
            continue

        tickers: list[str] = []
        seen: set[str] = set()

        for row in data_rows:
            cells = row.find_all(["th", "td"])
            if ticker_idx >= len(cells):
                continue

            ticker = _normalize_ticker(cells[ticker_idx].get_text(" ", strip=True))
            if not ticker or ticker == "IMOEX":
                continue
            if not SHARE_TICKER_PATTERN.fullmatch(ticker):
                continue
            if ticker in seen:
                continue

            seen.add(ticker)
            tickers.append(ticker)

        if tickers:
            log.info(f"Получено тикеров со страницы SmartLab shares: {len(tickers)}")
            return tickers

    raise ValueError("На странице SmartLab shares не найдена таблица с тикерами.")


def _get_family_key(ticker: str, available_tickers: Set[str]) -> str:
    """
    Возвращает ключ семейства тикера для обычки и префов.

    :param ticker: Исходный тикер.
    :param available_tickers: Все доступные тикеры для текущего запуска.
    :returns: Ключ семейства.
    """
    normalized_ticker = _normalize_ticker(ticker)
    if normalized_ticker.endswith("P"):
        base_ticker = normalized_ticker[:-1]
        if base_ticker in available_tickers:
            return base_ticker

    pref_ticker = f"{normalized_ticker}P"
    if pref_ticker in available_tickers:
        return normalized_ticker
    return normalized_ticker


def _build_ticker_families(
    save_directory: str,
    report_paths: Dict[str, Path],
    source_tickers: list[str],
    tickers: Optional[list[str]] = None,
) -> list[dict[str, object]]:
    """
    Строит семейства тикеров для обновления с одной страницы эмитента.

    :param save_directory: Директория для локальных CSV SmartLab.
    :param report_paths: Словарь локальных CSV.
    :param source_tickers: Список тикеров со страницы SmartLab shares.
    :param tickers: Необязательный список тикеров для выборочного запуска.
    :returns: Список словарей с описанием семейств.
    """
    requested_tickers = None
    if tickers is not None:
        requested_tickers = {_normalize_ticker(ticker) for ticker in tickers}

    output_directory = Path(save_directory)
    available_tickers = {_normalize_ticker(ticker) for ticker in source_tickers}
    families: dict[str, dict[str, object]] = {}
    for ticker in sorted(available_tickers):
        family_key = _get_family_key(ticker=ticker, available_tickers=available_tickers)
        family = families.setdefault(
            family_key,
            {
                "family_key": family_key,
                "members": [],
            },
        )
        csv_path = report_paths.get(ticker, output_directory / f"{ticker}.csv")
        family["members"].append((ticker, csv_path))

    family_list = []
    for family_key in sorted(families):
        family = families[family_key]
        members: list[tuple[str, Path]] = sorted(family["members"], key=lambda item: item[0])
        member_tickers = [ticker for ticker, _ in members]
        family["members"] = members
        family["candidate_tickers"] = _build_family_candidates(member_tickers=member_tickers)

        if requested_tickers is not None and not any(ticker in requested_tickers for ticker in member_tickers):
            continue

        family_list.append(family)

    return family_list


def _build_family_candidates(member_tickers: list[str]) -> list[str]:
    """
    Возвращает порядок тикеров-кандидатов для поиска рабочей страницы SmartLab.

    :param member_tickers: Тикеры внутри одного семейства.
    :returns: Список тикеров-кандидатов без дублей.
    """
    normalized_members = sorted({_normalize_ticker(ticker) for ticker in member_tickers})
    ordinary = [ticker for ticker in normalized_members if not ticker.endswith("P")]
    preferred = [ticker for ticker in normalized_members if ticker.endswith("P")]

    ordered_candidates = ordinary + preferred
    seen = set()
    result = []
    for ticker in ordered_candidates:
        if ticker in seen:
            continue
        seen.add(ticker)
        result.append(ticker)
    return result


def _build_report_url(ticker: str) -> str:
    """
    Формирует URL страницы годовой отчётности SmartLab для тикера.

    :param ticker: Тикер компании.
    :returns: Ссылка на страницу SmartLab.
    """
    return SMARTLAB_YEARLY_REPORT_URL.format(ticker=ticker)


def _fetch_company_page(page_url: str, timeout: int = 30) -> str:
    """
    Загружает HTML страницы компании на SmartLab.

    :param page_url: URL страницы годовой отчётности.
    :param timeout: Таймаут запроса в секундах.
    :returns: HTML страницы.
    :raises requests.RequestException: При ошибках сети или HTTP.
    """
    response = requests.get(page_url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _fetch_company_table(ticker: str, timeout: int = 30) -> tuple[str, pd.DataFrame]:
    """
    Загружает и парсит таблицу SmartLab для указанного тикера.

    :param ticker: Тикер, по которому нужно открыть страницу.
    :param timeout: Таймаут HTTP-запроса.
    :returns: Кортеж ``(page_url, page_df)``.
    """
    page_url = _build_report_url(ticker)
    html = _fetch_company_page(page_url=page_url, timeout=timeout)
    page_df = _extract_financial_table(html)
    return page_url, page_df


def _resolve_family_page(
    family_key: str,
    member_tickers: list[str],
    timeout: int = 30,
) -> dict[str, object]:
    """
    Находит рабочую каноническую страницу SmartLab для семейства тикеров.

    :param family_key: Ключ семейства.
    :param member_tickers: Список тикеров семейства.
    :param timeout: Таймаут HTTP-запроса.
    :returns: Информация о найденной странице и распарсенной таблице.
    :raises requests.RequestException: Если ни один URL не открылся.
    :raises ValueError: Если страница открылась, но таблица не найдена.
    """
    candidates = _build_family_candidates(member_tickers=member_tickers)
    last_error: Optional[Exception] = None

    for candidate in candidates:
        try:
            page_url, page_df = _fetch_company_table(ticker=candidate, timeout=timeout)
            return {
                "resolved_ticker": candidate,
                "page_url": page_url,
                "page_df": page_df,
            }
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                last_error = error
                continue
            raise
        except ValueError as error:
            last_error = error
            continue

    if last_error is not None:
        raise last_error
    raise ValueError(f"Не удалось найти рабочую страницу SmartLab для семейства {family_key}.")


def _extract_period_columns_from_row(row: Iterable[str]) -> list[tuple[int, str]]:
    """
    Извлекает из строки заголовка позиции колонок периодов (годы и LTM).

    :param row: Последовательность текстов ячеек.
    :returns: Список кортежей ``(index, period)`` в исходном порядке.
    """
    periods = []
    for idx, cell in enumerate(row):
        text = _normalize_text(cell)
        if _is_year_column(text):
            periods.append((idx, text))
            continue
        if _is_ltm_column(text):
            periods.append((idx, LTM_COLUMN))
    return periods


def _build_indicator_name(parts: list[str]) -> str:
    """
    Собирает читаемое имя показателя из левых ячеек строки таблицы.

    :param parts: Левая часть строки без значений периодов.
    :returns: Название показателя.
    """
    filtered_parts = [part for part in (_normalize_text(part) for part in parts) if part and part != "?"]
    if not filtered_parts:
        return ""

    if len(filtered_parts) == 1:
        return filtered_parts[0]

    indicator = filtered_parts[0]
    unit = filtered_parts[1]

    if unit and unit not in indicator:
        return f"{indicator}, {unit}"
    return indicator


def _parse_table_with_bs4(html: str) -> pd.DataFrame:
    """
    Разбирает HTML-таблицу SmartLab в DataFrame, близкий к исходному CSV.

    :param html: HTML страницы компании.
    :returns: DataFrame со столбцом показателя и колонками периодов.
    :raises ValueError: Если финансовая таблица не найдена.
    """
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue

            row: list[str] = []
            for cell in cells:
                text = _normalize_text(cell.get_text(" ", strip=True))
                colspan = int(cell.get("colspan", 1) or 1)
                row.extend([text] * colspan)
            if any(cell for cell in row):
                rows.append(row)

        if not rows:
            continue

        header_row_idx = None
        period_columns: list[tuple[int, str]] = []
        for idx, row in enumerate(rows):
            row_periods = _extract_period_columns_from_row(row)
            if len(row_periods) >= 2:
                header_row_idx = idx
                period_columns = row_periods
                break

        if header_row_idx is None:
            continue

        indicators = {_normalize_text(row[0]) for row in rows[header_row_idx + 1:] if row}
        if "Дата отчета" not in indicators or "Валюта отчета" not in indicators:
            continue

        periods = [period for _, period in period_columns]
        period_indexes = [column_idx for column_idx, _ in period_columns]
        first_period_idx = period_indexes[0]
        records: list[dict[str, str]] = []
        skip_rows = {"Финансовый отчет", "Годовой отчет", "Презентация"}

        for row in rows[header_row_idx + 1:]:
            if len(row) <= first_period_idx:
                continue

            leading_cells = row[:first_period_idx]
            indicator = _build_indicator_name(leading_cells)

            if not indicator or indicator in skip_rows:
                continue

            record = {INDICATOR_COLUMN: indicator}
            for column_idx, period in period_columns:
                value = row[column_idx] if column_idx < len(row) else ""
                record[period] = _normalize_text(value)

            non_empty_values = [record.get(period, "") for period in periods if record.get(period, "")]
            if non_empty_values and all(value == indicator for value in non_empty_values):
                continue

            if any(record.get(period, "") for period in periods):
                records.append(record)

        if records:
            result = pd.DataFrame(records)
            ordered_columns = [INDICATOR_COLUMN, *periods]
            return result.reindex(columns=ordered_columns).fillna("")

    raise ValueError("На странице SmartLab не найдена таблица с годовой отчётностью.")


def _extract_financial_table(html: str) -> pd.DataFrame:
    """
    Возвращает таблицу годовой отчётности SmartLab.

    :param html: HTML страницы компании.
    :returns: DataFrame с показателями и периодами.
    """
    try:
        return _parse_table_with_bs4(html)
    except ValueError:
        pass

    try:
        tables = pd.read_html(StringIO(html), keep_default_na=False)
    except ValueError:
        tables = []

    for table in tables:
        candidate = table.copy()
        candidate.columns = [_normalize_header_value(column) for column in candidate.columns]
        candidate = candidate.fillna("").astype(str)
        candidate = candidate.apply(lambda column: column.map(_normalize_text))

        if not candidate.empty and candidate.columns.tolist():
            columns = candidate.columns.tolist()
            if columns:
                indicator_column = columns[0]
                periods = []
                for column in columns[1:]:
                    if _is_year_column(column):
                        periods.append(column)
                        continue
                    if _is_ltm_column(column):
                        periods.append(LTM_COLUMN)
                if len(periods) >= 2:
                    normalized = candidate.rename(columns={indicator_column: INDICATOR_COLUMN})
                    normalized = normalized[[INDICATOR_COLUMN, *periods]]
                    indicators = set(normalized[INDICATOR_COLUMN].tolist())
                    if "Дата отчета" in indicators and "Валюта отчета" in indicators:
                        return normalized.fillna("")

    raise ValueError("На странице SmartLab не найдена таблица с годовой отчётностью.")


def _load_local_report(csv_path: Path) -> pd.DataFrame:
    """
    Загружает локальный CSV SmartLab в DataFrame со строковыми значениями.

    :param csv_path: Путь к локальному CSV.
    :returns: DataFrame в исходном широком формате.
    """
    df = pd.read_csv(
        csv_path,
        sep=";",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    first_column = df.columns[0]
    df = df.rename(columns={first_column: INDICATOR_COLUMN}).fillna("")
    df[INDICATOR_COLUMN] = df[INDICATOR_COLUMN].map(_normalize_text)
    return df


def _align_page_indicators(page_df: pd.DataFrame, local_df: pd.DataFrame) -> pd.DataFrame:
    """
    Приводит названия показателей страницы к тем, что уже используются в локальном CSV.

    :param page_df: Таблица, полученная со страницы SmartLab.
    :param local_df: Локальный CSV по этому тикеру.
    :returns: Копия ``page_df`` с выровненными названиями показателей.
    """
    result = page_df.copy()
    local_indicators = local_df[INDICATOR_COLUMN].tolist()
    normalized_local = {
        _normalize_indicator_for_match(indicator): indicator
        for indicator in local_indicators
    }

    def _match_existing_indicator(page_indicator: str) -> str:
        normalized = _normalize_indicator_for_match(page_indicator)
        if normalized in normalized_local:
            return normalized_local[normalized]

        parts = [part.strip() for part in page_indicator.split(",")]
        for idx in range(len(parts) - 1, 0, -1):
            candidate_indicator = ", ".join(parts[:idx]).strip()
            normalized_candidate = _normalize_indicator_for_match(candidate_indicator)
            if normalized_candidate in normalized_local:
                return normalized_local[normalized_candidate]
        return page_indicator

    aligned_indicators = []
    for indicator in result[INDICATOR_COLUMN]:
        aligned_indicators.append(_match_existing_indicator(indicator))

    result[INDICATOR_COLUMN] = aligned_indicators
    return result


def _sort_periods(periods: Iterable[str]) -> list[str]:
    """
    Сортирует периоды в привычном порядке SmartLab: годы по возрастанию, затем LTM.

    :param periods: Набор периодов.
    :returns: Отсортированный список периодов без дублей.
    """
    normalized_periods = []
    seen = set()
    for period in periods:
        normalized = _normalize_period_name(period)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_periods.append(normalized)

    year_periods = sorted([period for period in normalized_periods if _is_year_column(period)], key=int)
    if LTM_COLUMN in normalized_periods:
        year_periods.append(LTM_COLUMN)
    return year_periods


def _resolve_requested_periods(
    page_df: pd.DataFrame,
    period_columns: list[str],
) -> list[str]:
    """
    Определяет, какие периоды нужно добавить или обновить в локальном CSV.

    В итоговый список попадают только периоды, которые явно запросил пользователь
    и которые реально присутствуют на странице SmartLab.

    :param page_df: Таблица, полученная со страницы SmartLab.
    :param period_columns: Список периодов, которые нужно синхронизировать.
    :returns: Список периодов для записи в локальный CSV.
    """
    requested_periods = _sort_periods(period_columns)
    page_periods = {_normalize_period_name(column) for column in page_df.columns if _is_year_column(column) or _is_ltm_column(column)}
    available_periods = [period for period in requested_periods if period in page_periods]
    return available_periods


def _merge_periods(
    local_df: pd.DataFrame,
    page_df: pd.DataFrame,
    periods_to_sync: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    """
    Добавляет или обновляет указанные периоды в локальном CSV.

    :param local_df: Локальный CSV с полной историей.
    :param page_df: Таблица, полученная со страницы SmartLab.
    :param periods_to_sync: Список периодов для добавления или обновления.
    :returns: Кортеж ``(updated_df, new_indicators)``.
    """
    local_order = local_df[INDICATOR_COLUMN].tolist()
    page_order = page_df[INDICATOR_COLUMN].tolist()

    local_indexed = local_df.set_index(INDICATOR_COLUMN)
    page_indexed = page_df.set_index(INDICATOR_COLUMN)

    new_indicators = [indicator for indicator in page_order if indicator not in local_indexed.index]
    if new_indicators:
        extra_rows = pd.DataFrame("", index=new_indicators, columns=local_indexed.columns)
        local_indexed = pd.concat([local_indexed, extra_rows], axis=0)

    for period in _sort_periods(periods_to_sync):
        local_indexed[period] = ""
        if period in page_indexed.columns:
            local_indexed.loc[page_indexed.index, period] = page_indexed[period]

    ordered_indicators = [indicator for indicator in local_order if indicator in local_indexed.index]
    ordered_indicators.extend(indicator for indicator in page_order if indicator in new_indicators)
    local_indexed = local_indexed.reindex(ordered_indicators)

    ordered_columns = _sort_periods(local_indexed.columns)
    local_indexed = local_indexed.reindex(columns=ordered_columns, fill_value="")
    local_indexed.index.name = INDICATOR_COLUMN

    return local_indexed.reset_index(), new_indicators


def _save_local_report(csv_path: Path, df: pd.DataFrame) -> None:
    """
    Сохраняет обновлённый DataFrame обратно в CSV SmartLab.

    :param csv_path: Путь к локальному CSV.
    :param df: Подготовленный DataFrame для сохранения.
    """
    save_df = df.fillna("").copy()
    save_df.columns = ["", *save_df.columns[1:]]
    save_df.to_csv(csv_path, sep=";", index=False, encoding="utf-8-sig")


def _build_new_local_report(page_df: pd.DataFrame, periods_to_sync: list[str]) -> pd.DataFrame:
    """
    Собирает новый локальный CSV из страницы SmartLab для тикера, которого ещё нет локально.

    :param page_df: Таблица, полученная со страницы SmartLab.
    :param periods_to_sync: Периоды, которые нужно сохранить в CSV.
    :returns: DataFrame в формате локального CSV.
    """
    ordered_columns = [INDICATOR_COLUMN, *_sort_periods(periods_to_sync)]
    return page_df.reindex(columns=ordered_columns).fillna("")


def _update_one_report(
    csv_path: Path,
    page_df: pd.DataFrame,
    period_columns: list[str],
) -> Optional[dict[str, object]]:
    """
    Обновляет один локальный CSV отчёт по данным со страницы SmartLab.

    :param csv_path: Путь к существующему CSV тикера.
    :param page_df: Таблица со страницы канонического тикера семейства.
    :param period_columns: Список периодов для добавления или обновления.
    :returns: Словарь с результатом обновления или ``None``, если обновление не потребовалось.
    """
    ticker = csv_path.stem
    periods_to_sync = _resolve_requested_periods(
        page_df=page_df,
        period_columns=period_columns,
    )

    if not periods_to_sync:
        return None

    if not csv_path.exists():
        created_df = _build_new_local_report(page_df=page_df, periods_to_sync=periods_to_sync)
        _save_local_report(csv_path=csv_path, df=created_df)
        return {
            "ticker": ticker,
            "path": str(csv_path),
            "updated_periods": periods_to_sync,
            "new_indicators": created_df[INDICATOR_COLUMN].tolist(),
            "created": True,
        }

    local_df = _load_local_report(csv_path)
    page_df = _align_page_indicators(page_df=page_df, local_df=local_df)

    updated_df, new_indicators = _merge_periods(
        local_df=local_df,
        page_df=page_df,
        periods_to_sync=periods_to_sync,
    )
    _save_local_report(csv_path=csv_path, df=updated_df)
    return {
        "ticker": ticker,
        "path": str(csv_path),
        "updated_periods": periods_to_sync,
        "new_indicators": new_indicators,
        "created": False,
    }


def scrape_and_download(
    save_directory: str,
    period_columns: list[str],
    min_delay: float = 5,
    max_delay: float = 10,
    tickers: Optional[list[str]] = None,
) -> Set[str]:
    """
    Инкрементально обновляет локальные CSV SmartLab по списку бумаг со страницы shares.

    Источником тикеров служит таблица на странице ``https://smart-lab.ru/q/shares/``.
    Тикеры объединяются в семейства эмитента, например ``SBER/SBERP`` или
    ``RTKM/RTKMP``. Для семейства ищется одна каноническая страница SmartLab,
    таблица с неё используется для обновления всех локальных CSV этого семейства.
    Если для тикера ещё нет локального CSV, он будет создан. Какие именно периоды
    нужно добавить или обновить, пользователь задаёт явно через ``period_columns``.

    :param save_directory: Директория с локальными CSV SmartLab.
    :param period_columns: Список периодов SmartLab для добавления или обновления,
        например ``["2025"]`` или ``["2025", "LTM"]``.
    :param min_delay: Минимальная задержка между запросами к страницам компаний.
    :param max_delay: Максимальная задержка между запросами к страницам компаний.
    :param tickers: Необязательный список тикеров для выборочного запуска.
    :returns: Множество путей к обновлённым CSV файлам.
    """
    requested_periods = _sort_periods(period_columns)
    if not requested_periods:
        raise ValueError("Нужно передать хотя бы один период в period_columns.")

    report_paths = _get_existing_report_paths(save_directory)
    source_tickers = _fetch_share_tickers()
    families = _build_ticker_families(
        save_directory=save_directory,
        report_paths=report_paths,
        source_tickers=source_tickers,
        tickers=tickers,
    )
    updated_files: Set[str] = set()

    for idx, family in enumerate(families, start=1):
        family_key: str = family["family_key"]  # type: ignore[assignment]
        members: list[tuple[str, Path]] = family["members"]  # type: ignore[assignment]
        member_tickers = [ticker for ticker, _ in members]
        try:
            tickers_string = ", ".join(member_tickers)
            log.info(f"[{idx}/{len(families)}] Проверка семейства {family_key}: {tickers_string}")
            print(f"[{idx}/{len(families)}] Проверка семейства {family_key}: {tickers_string}")

            resolved = _resolve_family_page(
                family_key=family_key,
                member_tickers=member_tickers,
            )
            resolved_ticker = resolved["resolved_ticker"]
            page_df = resolved["page_df"]
            log.info(f"  - Каноническая страница SmartLab: {resolved_ticker}")
            print(f"  - Каноническая страница SmartLab: {resolved_ticker}")

            family_has_updates = False
            for ticker, csv_path in members:
                result = _update_one_report(
                    csv_path=csv_path,
                    page_df=page_df.copy(),
                    period_columns=requested_periods,
                )
                if result is None:
                    periods_string = ", ".join(requested_periods)
                    log.info(f"    - Запрошенных периодов нет на странице или в обновлении не требуется: {ticker} [{periods_string}]")
                    print(f"    - Запрошенных периодов нет на странице или в обновлении не требуется: {ticker} [{periods_string}]")
                    continue

                family_has_updates = True
                updated_files.add(result["path"])
                periods_string = ", ".join(result["updated_periods"])
                if result["created"]:
                    log.info(f"    + Создан CSV и записаны периоды [{periods_string}] для {ticker}")
                    print(f"    + Создан CSV и записаны периоды [{periods_string}] для {ticker}")
                else:
                    log.info(f"    + Обновлены периоды [{periods_string}] в {ticker}")
                    print(f"    + Обновлены периоды [{periods_string}] в {ticker}")

                if not result["created"] and result["new_indicators"]:
                    indicators_string = ", ".join(result["new_indicators"])
                    log.info(f"    + Добавлены новые показатели: {indicators_string}")

            if not family_has_updates:
                log.info(f"  - В семействе {family_key} обновлений не найдено")

            if idx < len(families):
                _apply_delay(min_delay=min_delay, max_delay=max_delay)

        except requests.exceptions.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else "unknown"
            if status_code == 429:
                log.error(f"  ! SmartLab вернул 429 для семейства {family_key}. Пауза 10 секунд.")
                print(f"  ! SmartLab вернул 429 для семейства {family_key}. Пауза 10 секунд.")
                time.sleep(10)
            else:
                log.error(f"  ! HTTP ошибка {status_code} для семейства {family_key}: {error}")
                print(f"  ! HTTP ошибка {status_code} для семейства {family_key}: {error}")
        except Exception as error:
            log.error(f"  ! Ошибка обновления семейства {family_key}: {error}")
            print(f"  ! Ошибка обновления семейства {family_key}: {error}")

    return updated_files


if __name__ == "__main__":
    log.init("Обновление локальных CSV SmartLab")
    scrape_and_download(
        period_columns=["2025"],
        min_delay=5,
        max_delay=10,
        save_directory=r"./support_files/scrapper_reports")
