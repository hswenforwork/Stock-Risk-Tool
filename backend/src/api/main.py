"""台股回測系統 API。"""

from fastapi import FastAPI

from backtest import BacktestSettings, PerformanceReport, run_backtest

from .sample_data import SAMPLE_BARS, SAMPLE_STRATEGY

app = FastAPI(title="台股回測系統")


@app.post("/api/backtests")
def create_backtest(settings: BacktestSettings) -> PerformanceReport:
    return run_backtest(SAMPLE_STRATEGY, SAMPLE_BARS, settings)
