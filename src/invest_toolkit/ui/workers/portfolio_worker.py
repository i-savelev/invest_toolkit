from invest_toolkit.ui.workers.base_worker import BaseWorker


class LoadTickersWorker(BaseWorker):
    def __init__(self, sber_path, vtb_path, allocation_path, parent=None):
        super().__init__(parent)
        self._sber_path = sber_path
        self._vtb_path = vtb_path
        self._allocation_path = allocation_path

    def do_work(self):
        from invest_toolkit.utils import log
        from invest_toolkit.io import (
            read_sber, read_vtb, all_instruments_info, allocatin_table,
        )
        from invest_toolkit.core import summary_report

        log.init("Загрузка тикеров для ребалансировки")

        # force_refresh=True → свежие цены при каждой загрузке тикеров
        all_info = all_instruments_info(force_refresh=True)

        sber = read_sber(self._sber_path)
        vtb = read_vtb(self._vtb_path)
        summary = summary_report([sber, vtb], all_info)
        alloc = allocatin_table(self._allocation_path)

        tickers = set()
        if "ticker" in summary.columns:
            tickers.update(summary["ticker"].dropna().astype(str).unique())
        if "ticker" in alloc.columns:
            tickers.update(alloc["ticker"].dropna().astype(str).unique())
        tickers.discard("")

        log.info(f"Уникальных тикеров: {len(tickers)}")
        return sorted(tickers)


class RunReportWorker(BaseWorker):
    """Запускает полный portfolio_report."""

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self._params = params

    def do_work(self):
        from invest_toolkit.orchestration import portfolio_report
        portfolio_report(**self._params)
        return self._params.get("report_save_path", "")