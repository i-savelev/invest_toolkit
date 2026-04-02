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
LTM_COLUMN = "LTM"
INDICATOR_COLUMN = "__indicator__"
SMARTLAB_YEARLY_REPORT_URL = "https://smart-lab.ru/q/{ticker}/f/y/"

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
    return re.sub(r"\s+", " ", text)


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
    :raises ValueError: Если директория не существует или не содержит CSV.
    """
    directory = Path(save_directory)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Директория не найдена: {save_directory}")

    csv_paths = sorted(directory.glob("*.csv"))
    if not csv_paths:
        raise ValueError(f"В директории нет CSV файлов: {save_directory}")

    reports = {_normalize_ticker(path.stem): path for path in csv_paths}
    log.info(f"Найдено локальных отчётов SmartLab: {len(reports)}")
    return reports


def _get_family_key(ticker: str, report_paths: Dict[str, Path]) -> str:
    """
    Возвращает ключ семейства тикера для обычки и префов.

    :param ticker: Исходный тикер.
    :param report_paths: Все доступные локальные CSV.
    :returns: Ключ семейства.
    """
    normalized_ticker = _normalize_ticker(ticker)
    if normalized_ticker.endswith("P"):
        base_ticker = normalized_ticker[:-1]
        if base_ticker in report_paths:
            return base_ticker

    pref_ticker = f"{normalized_ticker}P"
    if pref_ticker in report_paths:
        return normalized_ticker
    return normalized_ticker


def _build_ticker_families(
    report_paths: Dict[str, Path],
    tickers: Optional[list[str]] = None,
) -> list[dict[str, object]]:
    """
    Строит семейства тикеров для обновления с одной страницы эмитента.

    :param report_paths: Словарь локальных CSV.
    :param tickers: Необязательный список тикеров для выборочного запуска.
    :returns: Список словарей с описанием семейств.
    """
    requested_tickers = None
    if tickers is not None:
        requested_tickers = {_normalize_ticker(ticker) for ticker in tickers}

    families: dict[str, dict[str, object]] = {}
    for ticker, csv_path in sorted(report_paths.items()):
        family_key = _get_family_key(ticker=ticker, report_paths=report_paths)
        family = families.setdefault(
            family_key,
            {
                "family_key": family_key,
                "members": [],
            },
        )
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


def _extract_periods_from_row(row: Iterable[str]) -> list[str]:
    """
    Извлекает из строки заголовка набор периодов (годы и LTM).

    :param row: Последовательность текстов ячеек.
    :returns: Список периодов в исходном порядке.
    """
    periods = []
    for cell in row:
        text = _normalize_text(cell)
        if _is_year_column(text) or text == LTM_COLUMN:
            periods.append(text)
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

            row = [_normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if any(cell for cell in row):
                rows.append(row)

        if not rows:
            continue

        header_row_idx = None
        periods: list[str] = []
        for idx, row in enumerate(rows):
            row_periods = _extract_periods_from_row(row)
            if len(row_periods) >= 2:
                header_row_idx = idx
                periods = row_periods
                break

        if header_row_idx is None:
            continue

        indicators = {_normalize_text(row[0]) for row in rows[header_row_idx + 1:] if row}
        if "Дата отчета" not in indicators or "Валюта отчета" not in indicators:
            continue

        records: list[dict[str, str]] = []
        skip_rows = {"Финансовый отчет", "Годовой отчет", "Презентация"}

        for row in rows[header_row_idx + 1:]:
            if len(row) <= len(periods):
                continue

            leading_cells = row[:-len(periods)]
            value_cells = row[-len(periods):]
            indicator = _build_indicator_name(leading_cells)

            if not indicator or indicator in skip_rows:
                continue

            record = {INDICATOR_COLUMN: indicator}
            record.update({period: _normalize_text(value) for period, value in zip(periods, value_cells)})

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
                periods = [column for column in columns[1:] if _is_year_column(column) or column == LTM_COLUMN]
                if len(periods) >= 2:
                    normalized = candidate.rename(columns={indicator_column: INDICATOR_COLUMN})
                    normalized = normalized[[INDICATOR_COLUMN, *periods]]
                    indicators = set(normalized[INDICATOR_COLUMN].tolist())
                    if "Дата отчета" in indicators and "Валюта отчета" in indicators:
                        return normalized.fillna("")

    return _parse_table_with_bs4(html)


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


def _get_new_years(page_df: pd.DataFrame, local_df: pd.DataFrame) -> list[str]:
    """
    Находит годовые столбцы, которых ещё нет в локальном CSV.

    :param page_df: Таблица, полученная со страницы SmartLab.
    :param local_df: Локальный CSV.
    :returns: Список новых годов в порядке возрастания.
    """
    local_years = {column for column in local_df.columns if _is_year_column(column)}
    page_years = [column for column in page_df.columns if _is_year_column(column)]
    new_years = [year for year in page_years if year not in local_years]
    return sorted(new_years, key=int)


def _merge_new_years(local_df: pd.DataFrame, page_df: pd.DataFrame, new_years: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    Добавляет в локальный CSV только отсутствующие годовые колонки со страницы.

    :param local_df: Локальный CSV с полной историей.
    :param page_df: Таблица, полученная со страницы SmartLab.
    :param new_years: Список новых годов для добавления.
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

    for year in new_years:
        local_indexed[year] = ""
        if year in page_indexed.columns:
            local_indexed.loc[page_indexed.index, year] = page_indexed[year]

    ordered_indicators = [indicator for indicator in local_order if indicator in local_indexed.index]
    ordered_indicators.extend(indicator for indicator in page_order if indicator in new_indicators)
    local_indexed = local_indexed.reindex(ordered_indicators)

    ordered_years = sorted([column for column in local_indexed.columns if _is_year_column(column)], key=int)
    ordered_columns = ordered_years
    if LTM_COLUMN in local_indexed.columns:
        ordered_columns.append(LTM_COLUMN)
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


def _update_one_report(csv_path: Path, page_df: pd.DataFrame) -> Optional[dict[str, object]]:
    """
    Обновляет один локальный CSV отчёт по данным со страницы SmartLab.

    :param csv_path: Путь к существующему CSV тикера.
    :param page_df: Таблица со страницы канонического тикера семейства.
    :returns: Словарь с результатом обновления или ``None``, если обновление не потребовалось.
    """
    ticker = csv_path.stem
    local_df = _load_local_report(csv_path)
    page_df = _align_page_indicators(page_df=page_df, local_df=local_df)
    new_years = _get_new_years(page_df=page_df, local_df=local_df)

    if not new_years:
        return None

    updated_df, new_indicators = _merge_new_years(
        local_df=local_df,
        page_df=page_df,
        new_years=new_years,
    )
    _save_local_report(csv_path=csv_path, df=updated_df)
    return {
        "ticker": ticker,
        "path": str(csv_path),
        "new_years": new_years,
        "new_indicators": new_indicators,
    }


def scrape_and_download(
    save_directory: str,
    min_delay: float = 5,
    max_delay: float = 10,
    tickers: Optional[list[str]] = None,
) -> Set[str]:
    """
    Инкрементально обновляет локальные CSV SmartLab по уже скачанным тикерам.

    Источником тикеров служат имена CSV-файлов в ``save_directory``. Тикеры объединяются
    в семейства эмитента, например ``SBER/SBERP`` или ``RTKM/RTKMP``. Для семейства
    ищется одна каноническая страница SmartLab, таблица с неё используется для обновления
    всех локальных CSV этого семейства. Уже существующие годы не перезаписываются.

    :param save_directory: Директория с локальными CSV SmartLab.
    :param min_delay: Минимальная задержка между запросами к страницам компаний.
    :param max_delay: Максимальная задержка между запросами к страницам компаний.
    :param tickers: Необязательный список тикеров для выборочного запуска.
    :returns: Множество путей к обновлённым CSV файлам.
    """
    report_paths = _get_existing_report_paths(save_directory)
    families = _build_ticker_families(report_paths=report_paths, tickers=tickers)
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
                result = _update_one_report(csv_path=csv_path, page_df=page_df.copy())
                if result is None:
                    log.info(f"    - Новых годовых колонок нет: {ticker}")
                    print(f"    - Новых годовых колонок нет: {ticker}")
                    continue

                family_has_updates = True
                updated_files.add(result["path"])
                years_string = ", ".join(result["new_years"])
                log.info(f"    + Добавлены годы [{years_string}] в {ticker}")
                print(f"    + Добавлены годы [{years_string}] в {ticker}")

                if result["new_indicators"]:
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
        min_delay=2,
        max_delay=5,
        save_directory=r"./support_files/scrapper_reports")
