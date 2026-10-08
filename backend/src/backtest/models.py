"""回測引擎的輸入與輸出型別。用語依 GLOSSARY.md。"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

STRATEGY_FORMAT_VERSION = 1

# 盤中零股交易開放日；回測區間不得早於這天（ADR 0005）
EARLIEST_START_DATE = date(2020, 10, 26)


class Bar(BaseModel):
    """一個交易日的日 K（原始股價）。close 為 0 代表當天沒有成交（停牌）。"""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class CloseVsSma(BaseModel):
    """條件積木：收盤價站上（above）或跌破（below）N 日均線。"""

    type: Literal["close_vs_sma"]
    op: Literal["above", "below"]
    period: int = Field(ge=1)


Condition = CloseVsSma


class Rule(BaseModel):
    """規則：條件組合 → 動作。"""

    action: Literal["entry", "exit"]
    condition: Condition


class Strategy(BaseModel):
    """策略 JSON（ADR 0006）：有順序的規則清單。"""

    version: Literal[1]
    rules: list[Rule] = Field(min_length=1)


class BacktestSettings(BaseModel):
    """回測設定。交易成本的預設值見規格 #2。"""

    initial_capital: float = Field(gt=0)
    start_date: date | None = None
    end_date: date | None = None
    lot: Literal["odd", "board"] = "odd"
    """成交單位：零股（1 股）或整張（1,000 股）。"""
    fee_discount: float = Field(default=0.6, ge=0, le=1)
    """手續費折扣，套用在法定費率 0.1425% 上。"""
    min_fee: float = Field(default=1, ge=0)
    """每筆最低手續費（元）。"""
    slippage: float = Field(default=0.001, ge=0, le=0.1)
    """滑價比例：買進價往上加、賣出價往下扣。"""
    is_etf: bool = False
    """標的是否為 ETF，決定證交稅率。"""

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.start_date is not None and self.start_date < EARLIEST_START_DATE:
            raise ValueError(f"回測區間最早只能從 {EARLIEST_START_DATE} 開始（盤中零股交易開放日）")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("回測結束日不得早於起始日")
        return self


class Trade(BaseModel):
    """一筆成交。"""

    date: date
    action: Literal["entry", "exit"]
    shares: int
    price: float
    """含滑價的成交價。"""
    fee: float
    tax: float
    delayed: bool
    """訊號是否因停牌而延後成交。"""


class PerformanceReport(BaseModel):
    """績效報告。"""

    initial_capital: float
    final_equity: float
    total_return: float
    trades: list[Trade]
