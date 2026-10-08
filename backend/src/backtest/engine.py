"""回測引擎：策略 JSON＋行情資料＋回測設定 → 績效報告。

純計算，不碰資料庫與網路。每個交易日收盤後由上往下比對規則，
只執行第一條成立的規則，在下一個交易日開盤成交（ADR 0007）。
"""

import math

from .models import BacktestSettings, Bar, Condition, PerformanceReport, Rule, Strategy


def run_backtest(
    strategy: Strategy, bars: list[Bar], settings: BacktestSettings
) -> PerformanceReport:
    cash = settings.initial_capital
    shares = 0
    pending: Rule | None = None

    for i, bar in enumerate(bars):
        if pending is not None:
            if pending.action == "entry":
                shares = math.floor(cash / bar.open)
                cash -= shares * bar.open
            else:
                cash += shares * bar.open
                shares = 0
            pending = None

        pending = _first_matching_rule(strategy, bars, i, holding=shares > 0)

    final_equity = cash + shares * bars[-1].close if bars else cash
    return PerformanceReport(
        initial_capital=settings.initial_capital,
        final_equity=final_equity,
        total_return=final_equity / settings.initial_capital - 1,
    )


def _first_matching_rule(strategy: Strategy, bars: list[Bar], i: int, holding: bool) -> Rule | None:
    for rule in strategy.rules:
        applicable = (rule.action == "entry") != holding
        if applicable and _condition_holds(rule.condition, bars, i):
            return rule
    return None


def _condition_holds(condition: Condition, bars: list[Bar], i: int) -> bool:
    period = condition.period
    if i + 1 < period:
        return False
    sma = sum(b.close for b in bars[i + 1 - period : i + 1]) / period
    close = bars[i].close
    return close > sma if condition.op == "above" else close < sma
