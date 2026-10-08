"""回測引擎的輸入與輸出型別。用語依 GLOSSARY.md。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

STRATEGY_FORMAT_VERSION = 1


class Bar(BaseModel):
    """一個交易日的日 K（原始股價）。"""

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
    initial_capital: float = Field(gt=0)


class PerformanceReport(BaseModel):
    """績效報告。"""

    initial_capital: float
    final_equity: float
    total_return: float
