"""回測引擎：策略 JSON＋行情資料＋回測設定 → 績效報告。

純計算，不碰資料庫與網路。每個交易日收盤後由上往下比對規則，
只執行第一條成立的規則，在下一個有成交的交易日開盤成交（ADR 0007）。
回測起始日以前的行情只用來讓條件積木暖機。
"""

import math

from .models import (
    BacktestSettings,
    Bar,
    Condition,
    PerformanceReport,
    Rule,
    Strategy,
    Trade,
)

FEE_RATE = 0.001425
STOCK_TAX_RATE = 0.003
ETF_TAX_RATE = 0.001
BOARD_LOT = 1000


def run_backtest(
    strategy: Strategy, bars: list[Bar], settings: BacktestSettings
) -> PerformanceReport:
    account = _Account(settings)
    history: list[Bar] = []  # 有成交的交易日，供條件積木計算
    pending: Rule | None = None
    delayed = False
    last_close: float | None = None

    for bar in bars:
        if settings.end_date and bar.date > settings.end_date:
            break
        if bar.close <= 0:
            delayed = pending is not None
            continue

        if pending is not None:
            account.execute(pending, bar, delayed)
            pending, delayed = None, False

        history.append(bar)
        if settings.start_date is None or bar.date >= settings.start_date:
            last_close = bar.close
            pending = _first_matching_rule(strategy, history, holding=account.shares > 0)

    final_equity = account.cash + account.shares * (last_close or 0)
    return PerformanceReport(
        initial_capital=settings.initial_capital,
        final_equity=final_equity,
        total_return=final_equity / settings.initial_capital - 1,
        trades=account.trades,
    )


class _Account:
    def __init__(self, settings: BacktestSettings):
        self.settings = settings
        self.cash = settings.initial_capital
        self.shares = 0
        self.trades: list[Trade] = []

    def execute(self, rule: Rule, bar: Bar, delayed: bool) -> None:
        if rule.action == "entry":
            self._buy(bar, delayed)
        else:
            self._sell(bar, delayed)

    def _buy(self, bar: Bar, delayed: bool) -> None:
        price = bar.open * (1 + self.settings.slippage)
        unit = BOARD_LOT if self.settings.lot == "board" else 1
        rate = FEE_RATE * self.settings.fee_discount
        shares = math.floor(self.cash / (price * (1 + rate)) / unit) * unit
        while shares > 0 and shares * price + self._fee(shares * price) > self.cash:
            shares -= unit
        if shares <= 0:
            return

        amount = shares * price
        fee = self._fee(amount)
        self.cash -= amount + fee
        self.shares += shares
        self.trades.append(
            Trade(
                date=bar.date,
                action="entry",
                shares=shares,
                price=price,
                fee=fee,
                tax=0,
                delayed=delayed,
            )
        )

    def _sell(self, bar: Bar, delayed: bool) -> None:
        price = bar.open * (1 - self.settings.slippage)
        shares = self.shares
        amount = shares * price
        fee = self._fee(amount)
        tax = _floor(amount * (ETF_TAX_RATE if self.settings.is_etf else STOCK_TAX_RATE))
        self.cash += amount - fee - tax
        self.shares = 0
        self.trades.append(
            Trade(
                date=bar.date,
                action="exit",
                shares=shares,
                price=price,
                fee=fee,
                tax=tax,
                delayed=delayed,
            )
        )

    def _fee(self, amount: float) -> float:
        """手續費無條件捨去到元，但不低於最低手續費。"""
        return max(_floor(amount * FEE_RATE * self.settings.fee_discount), self.settings.min_fee)


def _floor(value: float) -> int:
    # 加上極小值，避免浮點誤差讓 2.0 變成 1.999… 被捨去成 1
    return math.floor(value + 1e-9)


def _first_matching_rule(strategy: Strategy, history: list[Bar], holding: bool) -> Rule | None:
    for rule in strategy.rules:
        applicable = (rule.action == "entry") != holding
        if applicable and _condition_holds(rule.condition, history):
            return rule
    return None


def _condition_holds(condition: Condition, history: list[Bar]) -> bool:
    period = condition.period
    if len(history) < period:
        return False
    sma = sum(b.close for b in history[-period:]) / period
    close = history[-1].close
    return close > sma if condition.op == "above" else close < sma
