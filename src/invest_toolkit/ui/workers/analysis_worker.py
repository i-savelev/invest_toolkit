from pathlib import Path

from invest_toolkit.ui.workers.base_worker import BaseWorker


class AnalysisDataWorker(BaseWorker):
    """Формирует all_stock_info и сохраняет в кэш."""

    def __init__(self, free_float_path: str, ir_path: str,
                 sl_stock_folder: str, cache_path: Path, parent=None):
        super().__init__(parent)
        self._free_float_path = free_float_path
        self._ir_path = ir_path
        self._sl_stock_folder = sl_stock_folder
        self._cache_path = cache_path

    def do_work(self):
        from invest_toolkit.utils import log
        from invest_toolkit.orchestration import all_stock_info

        log.init("Формирование данных для анализа компаний")

        df = all_stock_info(
            free_dloat_path=self._free_float_path,
            ir_path=self._ir_path,
            sl_stock_folder=self._sl_stock_folder,
        )

        # Сохраняем в кэш
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self._cache_path, index=False)
        log.info(f"Данные сохранены в кэш: {self._cache_path}")
        log.info(f"Тикеров: {df['ticker'].nunique()}, записей: {len(df)}")

        return df