"""回測引擎：策略 JSON＋行情資料＋回測設定 → 績效報告。

純計算，不碰資料庫與網路。每個交易日收盤後由上往下比對規則，
只執行第一條「適用且條件成立」的規則，在下一個有成交的交易日開盤成交。
買進採層模型、賣出採出場比例（ADR 0007）。
回測起始日以前的行情只用來讓條件積木暖機。
"""

import math

from . import indicators
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
EPSILON = 1e-9

BUY_ACTIONS = {"entry", "add"}


def run_backtest(
    strategy: Strategy, bars: list[Bar], settings: BacktestSettings
) -> PerformanceReport:
    bars = [b for b in bars if settings.end_date is None or b.date <= settings.end_date]
    market = _Market([b for b in bars if b.close > 0])  # 有成交的交易日，供條件積木計算
    account = _Account(strategy, settings)
    pending: Rule | None = None
    delayed = False
    last_close: float | None = None
    i = -1  # 目前是第幾個有成交的交易日

    for bar in bars:
        if bar.close <= 0:
            delayed = pending is not None
            continue
        i += 1

        if pending is not None:
            account.execute(pending, bar, delayed)
            pending, delayed = None, False

        if settings.start_date is None or bar.date >= settings.start_date:
            last_close = bar.close
            pending = _first_matching_rule(strategy, market, i, account)

    final_equity = account.cash + account.shares * (last_close or 0)
    return PerformanceReport(
        initial_capital=settings.initial_capital,
        final_equity=final_equity,
        total_return=final_equity / settings.initial_capital - 1,
        trades=account.trades,
    )


class _Account:
    """現金與一段持倉的狀態。"""

    def __init__(self, strategy: Strategy, settings: BacktestSettings):
        self.strategy = strategy
        self.settings = settings
        self.unit = BOARD_LOT if settings.lot == "board" else 1
        self.cash = settings.initial_capital
        self.trades: list[Trade] = []
        self._reset_position()

    def _reset_position(self) -> None:
        self.shares = 0
        self.planned_capital = 0.0  # 預計投入資金
        self.layers_filled = 0
        self.avg_cost = 0.0
        self.last_buy_price: float | None = None
        self.last_sell_price: float | None = None
        self.exit_base = 0  # 本輪出場開始時的持股
        self.batches_sold = 0  # 本輪已賣出的批數

    @property
    def holding(self) -> bool:
        return self.shares > 0

    def applicable(self, rule: Rule, close: float) -> bool:
        match rule.action:
            case "entry":
                return not self.holding
            case "add":
                # 現金買不起一個成交單位時不適用，以免每天佔掉執行機會、擋住後面的規則
                return (
                    self.holding
                    and self.layers_filled < len(self.strategy.entry_ratios)
                    and self.cash >= close * self.unit
                )
            case "exit":
                return self.holding and self.batches_sold == 0
            case "reduce":
                return self.holding and self.batches_sold > 0
            case _:  # stop_loss、take_profit
                return self.holding

    def execute(self, rule: Rule, bar: Bar, delayed: bool) -> None:
        if rule.action in BUY_ACTIONS:
            self._buy(rule, bar, delayed)
        elif rule.action == "stop_loss":
            self._sell(rule, bar, delayed, self.shares)
        else:
            self._sell(rule, bar, delayed, self._next_exit_batch())

    def _buy(self, rule: Rule, bar: Bar, delayed: bool) -> None:
        if rule.action == "entry":
            self.planned_capital = self.cash
        ratio = self.strategy.entry_ratios[self.layers_filled]
        budget = min(self.planned_capital * ratio, self.cash)
        price = bar.open * (1 + self.settings.slippage)

        shares = self._affordable_shares(budget, price)
        if shares <= 0:
            return

        amount = shares * price
        fee = self._fee(amount)
        self.cash -= amount + fee
        self.avg_cost = (self.avg_cost * self.shares + amount) / (self.shares + shares)
        self.shares += shares
        self.layers_filled += 1
        self.last_buy_price = price
        self.batches_sold = 0  # 加碼後，出場批次重新從第一批算
        self._record(rule, bar, delayed, self.layers_filled, shares, price, fee, 0)

    def _affordable_shares(self, budget: float, price: float) -> int:
        rate = FEE_RATE * self.settings.fee_discount
        shares = math.floor(budget / (price * (1 + rate)) / self.unit) * self.unit
        while shares > 0 and shares * price + self._fee(shares * price) > budget + EPSILON:
            shares -= self.unit
        return shares

    def _next_exit_batch(self) -> int:
        if self.batches_sold == 0:
            self.exit_base = self.shares
        ratios = self.strategy.exit_ratios
        if self.batches_sold >= len(ratios) - 1:
            return self.shares  # 最後一批賣出全部剩餘持股
        shares = math.floor(self.exit_base * ratios[self.batches_sold] / self.unit) * self.unit
        return min(max(shares, self.unit), self.shares)

    def _sell(self, rule: Rule, bar: Bar, delayed: bool, shares: int) -> None:
        price = bar.open * (1 - self.settings.slippage)
        amount = shares * price
        fee = self._fee(amount)
        tax = _floor(amount * (ETF_TAX_RATE if self.settings.is_etf else STOCK_TAX_RATE))
        self.cash += amount - fee - tax
        self.shares -= shares
        self.batches_sold += 1
        self.layers_filled = max(self.layers_filled - 1, 0)  # 釋出最上面一層
        self.last_sell_price = price
        self._record(rule, bar, delayed, self.batches_sold, shares, price, fee, tax)
        if not self.holding:
            self._reset_position()

    def _record(self, rule, bar, delayed, batch, shares, price, fee, tax) -> None:
        self.trades.append(
            Trade(
                date=bar.date,
                action=rule.action,
                batch=batch,
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
    return math.floor(value + EPSILON)


def _first_matching_rule(
    strategy: Strategy, market: "_Market", i: int, account: _Account
) -> Rule | None:
    close = market.closes[i]
    for rule in strategy.rules:
        if account.applicable(rule, close) and _holds(rule.condition, market, i, account):
            return rule
    return None


class _Market:
    """有成交的交易日行情，以及依參數快取的指標序列（只存在這次回測）。"""

    def __init__(self, bars: list[Bar]):
        self.closes = [b.close for b in bars]
        self.highs = [b.high for b in bars]
        self.lows = [b.low for b in bars]
        self.volumes = [b.volume for b in bars]
        self._cache: dict[tuple, object] = {}

    def _cached(self, key: tuple, compute):
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def sma(self, period: int) -> indicators.Series:
        return self._cached(("sma", period), lambda: indicators.sma(self.closes, period))

    def rsi(self, period: int) -> indicators.Series:
        return self._cached(("rsi", period), lambda: indicators.rsi(self.closes, period))

    def macd(self, fast: int, slow: int, signal: int):
        return self._cached(
            ("macd", fast, slow, signal),
            lambda: indicators.macd(self.closes, fast, slow, signal),
        )

    def kd(self, period: int):
        return self._cached(
            ("kd", period), lambda: indicators.kd(self.highs, self.lows, self.closes, period)
        )

    def bollinger(self, period: int, width: float):
        return self._cached(
            ("bollinger", period, width), lambda: indicators.bollinger(self.closes, period, width)
        )

    def volume_average(self, period: int) -> indicators.Series:
        return self._cached(
            ("volume_average", period), lambda: indicators.previous_average(self.volumes, period)
        )


def _holds(condition: Condition, market: _Market, i: int, account: _Account) -> bool:
    close = market.closes[i]
    match condition.type:
        case "all":
            return all(_holds(c, market, i, account) for c in condition.conditions)
        case "any":
            return any(_holds(c, market, i, account) for c in condition.conditions)
        case "close_vs_value":
            return _compare(close, condition.op, condition.value)
        case "close_vs_sma":
            return _compare(close, condition.op, market.sma(condition.period)[i])
        case "sma_cross":
            fast, slow = market.sma(condition.fast), market.sma(condition.slow)
            return _crossed(fast, slow, i, condition.op)
        case "rsi":
            return _compare(market.rsi(condition.period)[i], condition.op, condition.value)
        case "macd_cross":
            dif, dem = market.macd(condition.fast, condition.slow, condition.signal)
            return _crossed(dif, dem, i, condition.op)
        case "kd_cross":
            k, d = market.kd(condition.period)
            return _crossed(k, d, i, condition.op)
        case "kd_level":
            k, d = market.kd(condition.period)
            line = k if condition.line == "k" else d
            return _compare(line[i], condition.op, condition.value)
        case "bollinger":
            upper, lower = market.bollinger(condition.period, condition.std)
            if condition.op == "above_upper":
                return _compare(close, "above", upper[i])
            return _compare(close, "below", lower[i])
        case "volume_vs_avg":
            average = market.volume_average(condition.period)[i]
            if average is None:
                return False
            return _compare(market.volumes[i], condition.op, average * condition.multiple)
        case "price_vs_last_buy":
            return account.holding and _moved(close, account.last_buy_price, condition)
        case "price_vs_last_sell":
            reference = account.last_sell_price or account.avg_cost
            return account.holding and _moved(close, reference, condition)
        case "pnl_vs_avg_cost":
            op = "up" if condition.op == "gain" else "down"
            return account.holding and _moved(close, account.avg_cost, condition, op)
    raise ValueError(f"未知的條件積木：{condition.type}")


def _crossed(a: indicators.Series, b: indicators.Series, i: int, op: str) -> bool:
    """黃金交叉：前一天 a <= b、今天 a > b；死亡交叉：前一天 a >= b、今天 a < b。"""
    if i < 1 or None in (a[i], b[i], a[i - 1], b[i - 1]):
        return False
    if op == "golden":
        return a[i - 1] <= b[i - 1] and a[i] > b[i]
    return a[i - 1] >= b[i - 1] and a[i] < b[i]


def _compare(value: float | None, op: str, reference: float | None) -> bool:
    """指標還在暖機（None）時一律不成立。"""
    if value is None or reference is None:
        return False
    return value > reference if op == "above" else value < reference


def _moved(close: float, reference: float | None, condition, op: str | None = None) -> bool:
    """收盤價相對基準上漲（up）或下跌（down）至少 condition.pct。"""
    if not reference:
        return False
    if (op or condition.op) == "up":
        return close >= reference * (1 + condition.pct) - EPSILON
    return close <= reference * (1 - condition.pct) + EPSILON
