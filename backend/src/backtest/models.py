"""回測引擎的輸入與輸出型別。用語依 GLOSSARY.md。"""

from datetime import date
from typing import Annotated, Literal, Self

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


class SmaCross(BaseModel):
    """條件積木：短天期均線向上（golden，黃金交叉）或向下（death，死亡交叉）穿越長天期均線。"""

    type: Literal["sma_cross"]
    op: Literal["golden", "death"]
    fast: int = Field(ge=1)
    slow: int = Field(ge=2)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.fast >= self.slow:
            raise ValueError("均線交叉的短天期必須小於長天期")
        return self


class Rsi(BaseModel):
    """條件積木：N 日 RSI 高於（above）或低於（below）某數值。"""

    type: Literal["rsi"]
    period: int = Field(ge=2)
    op: Literal["above", "below"]
    value: float = Field(ge=0, le=100)


class MacdCross(BaseModel):
    """條件積木：MACD 的 DIF 向上（golden）或向下（death）穿越訊號線。"""

    type: Literal["macd_cross"]
    op: Literal["golden", "death"]
    fast: int = Field(default=12, ge=1)
    slow: int = Field(default=26, ge=2)
    signal: int = Field(default=9, ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.fast >= self.slow:
            raise ValueError("MACD 的快線天期必須小於慢線天期")
        return self


class KdCross(BaseModel):
    """條件積木：K 值向上（golden）或向下（death）穿越 D 值。"""

    type: Literal["kd_cross"]
    op: Literal["golden", "death"]
    period: int = Field(default=9, ge=2)


class KdLevel(BaseModel):
    """條件積木：K 值或 D 值高於（above）或低於（below）某數值。"""

    type: Literal["kd_level"]
    line: Literal["k", "d"]
    op: Literal["above", "below"]
    value: float = Field(ge=0, le=100)
    period: int = Field(default=9, ge=2)


class Bollinger(BaseModel):
    """條件積木：收盤價突破上軌（above_upper）或跌破下軌（below_lower）。"""

    type: Literal["bollinger"]
    op: Literal["above_upper", "below_lower"]
    period: int = Field(default=20, ge=2)
    std: float = Field(default=2, gt=0)


class VolumeVsAvg(BaseModel):
    """條件積木：當天成交量大於（above）或小於（below）前 N 日均量的某倍數。"""

    type: Literal["volume_vs_avg"]
    op: Literal["above", "below"]
    period: int = Field(ge=1)
    multiple: float = Field(gt=0)


class CloseVsValue(BaseModel):
    """條件積木：收盤價高於（above）或低於（below）固定價格。"""

    type: Literal["close_vs_value"]
    op: Literal["above", "below"]
    value: float = Field(ge=0)


class PriceVsLastBuy(BaseModel):
    """條件積木：收盤價比上一批買進價上漲（up）或下跌（down）至少 pct。空手時不成立。"""

    type: Literal["price_vs_last_buy"]
    op: Literal["up", "down"]
    pct: float = Field(gt=0)


class PriceVsLastSell(BaseModel):
    """條件積木：收盤價比本段持倉上一批賣出價上漲（up）或下跌（down）至少 pct。

    本段持倉還沒賣過時，以平均成本為基準。空手時不成立。
    """

    type: Literal["price_vs_last_sell"]
    op: Literal["up", "down"]
    pct: float = Field(gt=0)


class PnlVsAvgCost(BaseModel):
    """條件積木：以平均成本計算，獲利（gain）或虧損（loss）至少 pct。空手時不成立。"""

    type: Literal["pnl_vs_avg_cost"]
    op: Literal["gain", "loss"]
    pct: float = Field(gt=0)


class ConditionGroup(BaseModel):
    """條件群組：全部成立（all，且）或任一成立（any，或），可以任意巢狀。"""

    type: Literal["all", "any"]
    conditions: list["Condition"] = Field(min_length=1)


Condition = Annotated[
    CloseVsSma
    | SmaCross
    | Rsi
    | MacdCross
    | KdCross
    | KdLevel
    | Bollinger
    | VolumeVsAvg
    | CloseVsValue
    | PriceVsLastBuy
    | PriceVsLastSell
    | PnlVsAvgCost
    | ConditionGroup,
    Field(discriminator="type"),
]
ConditionGroup.model_rebuild()

Action = Literal["entry", "add", "reduce", "exit", "stop_loss", "take_profit"]

DEFAULT_RATIOS = (0.5, 0.3, 0.2)


def _check_ratios(name: str, ratios: list[float]) -> None:
    if not 1 <= len(ratios) <= 5:
        raise ValueError(f"{name}必須有 1 到 5 批")
    if any(r <= 0 for r in ratios):
        raise ValueError(f"{name}的每一批都必須大於 0")
    if abs(sum(ratios) - 1) > 1e-9:
        raise ValueError(f"{name}合計必須是 100%")


class Rule(BaseModel):
    """規則：條件組合 → 動作。"""

    action: Action
    condition: Condition


class Strategy(BaseModel):
    """策略 JSON（ADR 0006）：有順序的規則清單，加上進場比例與出場比例（ADR 0007）。"""

    version: Literal[1]
    rules: list[Rule] = Field(min_length=1)
    entry_ratios: list[float] = Field(default_factory=lambda: list(DEFAULT_RATIOS))
    exit_ratios: list[float] = Field(default_factory=lambda: list(DEFAULT_RATIOS))

    @model_validator(mode="after")
    def _check(self) -> Self:
        _check_ratios("進場比例", self.entry_ratios)
        _check_ratios("出場比例", self.exit_ratios)
        return self


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
    action: Action
    batch: int
    """買進時是第幾層，賣出時是本輪出場的第幾批（都從 1 起算）。"""
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
