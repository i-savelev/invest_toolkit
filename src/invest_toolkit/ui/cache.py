"""
Кэш для тяжёлых функций MOEX API на уровне UI.
"""

import time
import functools

_cache_store: dict = {}
CACHE_TTL_SECONDS = 3600


def setup_moex_cache() -> None:
    """
    Подменяет all_instruments_info на кэшированную версию во всех модулях,
    откуда её могут импортировать. Вызывать один раз при старте приложения.
    """
    from invest_toolkit.io import moex
    from invest_toolkit import io as io_pkg
    from invest_toolkit import orchestration
    from invest_toolkit.orchestration import workflows

    original_func = moex.all_instruments_info

    @functools.wraps(original_func)
    def cached_all_instruments_info(*args, force_refresh=False, **kwargs):
        now = time.time()

        if not force_refresh and "moex" in _cache_store:
            data, timestamp = _cache_store["moex"]
            age = now - timestamp
            if age < CACHE_TTL_SECONDS:
                from invest_toolkit.utils import log
                log.info(f"MOEX: использую кэш (возраст {age:.0f}с)")
                return data.copy()

        if force_refresh and "moex" in _cache_store:
            from invest_toolkit.utils import log
            log.info("MOEX: принудительное обновление кэша")

        result = original_func(*args, **kwargs)
        _cache_store["moex"] = (result, now)
        return result

    # Подменяем во ВСЕХ точках, откуда может идти импорт
    moex.all_instruments_info = cached_all_instruments_info
    io_pkg.all_instruments_info = cached_all_instruments_info
    workflows.all_instruments_info = cached_all_instruments_info

    # Верхний уровень пакета (from invest_toolkit import all_instruments_info)
    import invest_toolkit
    invest_toolkit.all_instruments_info = cached_all_instruments_info


def invalidate_moex_cache() -> None:
    """Принудительно сбрасывает кэш."""
    _cache_store.pop("moex", None)