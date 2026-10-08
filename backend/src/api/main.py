"""台股回測系統 API。"""

from fastapi import FastAPI

from backtest import BacktestSettings, PerformanceReport, Strategy, run_backtest

from .sample_data import SAMPLE_BARS, SAMPLE_STRATEGY

app = FastAPI(title="台股回測系統")


class BacktestRequest(BacktestSettings):
    """回測設定，可以另外附上策略 JSON；沒附時使用示範策略。"""

    strategy: Strategy | None = None


@app.post("/api/backtests")
def create_backtest(request: BacktestRequest) -> PerformanceReport:
    settings = BacktestSettings.model_validate(request.model_dump(exclude={"strategy"}))
    return run_backtest(request.strategy or SAMPLE_STRATEGY, SAMPLE_BARS, settings)
