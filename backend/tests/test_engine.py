"""回測引擎的行為測試：只透過 run_backtest 的輸入與輸出驗證。"""

from datetime import date, timedelta

import pytest

from backtest import BacktestSettings, Bar, Strategy, run_backtest

SMA3_STRATEGY = {
    "version": 1,
    "entry_ratios": [1],  # 一次全進、一次全出
    "exit_ratios": [1],
    "rules": [
        {"action": "entry", "condition": {"type": "close_vs_sma", "op": "above", "period": 3}},
        {"action": "exit", "condition": {"type": "close_vs_sma", "op": "below", "period": 3}},
    ],
}


def no_fee(initial_capital: float) -> BacktestSettings:
    """不收手續費、不計滑價的設定（證交稅依法固定，仍會扣）。"""
    return BacktestSettings(initial_capital=initial_capital, fee_discount=0, min_fee=0, slippage=0)


def make_bars(rows: list[tuple[float, float]]) -> list[Bar]:
    """以 (開盤價, 收盤價) 建立連續交易日的日 K。"""
    start = date(2021, 1, 4)  # 2021-01-04 起連續日期（不區分週末，引擎只看順序）
    return [
        Bar(
            date=start + timedelta(days=i),
            open=o,
            high=max(o, c),
            low=min(o, c),
            close=c,
            volume=1000,
        )
        for i, (o, c) in enumerate(rows)
    ]


def test_entry_and_exit_fill_at_next_day_open():
    # 收盤 10,10,10,13 → 第 4 天 3 日均線 11，13 > 11 觸發進場訊號
    # 第 5 天開盤 12 買進：floor(1000 / 12) = 83 股，剩 4 元
    # 第 6 天收盤 9，3 日均線 (13+12+9)/3 ≈ 11.33，9 < 11.33 觸發出場訊號
    # 第 7 天開盤 15 賣出：83 × 15 = 1245，證交稅 floor(1245 × 0.3%) = 3
    # 權益 4 + 1245 - 3 = 1246
    bars = make_bars([(10, 10), (10, 10), (10, 10), (10, 13), (12, 12), (12, 9), (15, 15)])

    report = run_backtest(Strategy.model_validate(SMA3_STRATEGY), bars, no_fee(1000))

    assert report.final_equity == pytest.approx(1246)
    assert report.total_return == pytest.approx(0.246)


def test_no_signal_keeps_cash_unchanged():
    bars = make_bars([(10, 10)] * 5)

    report = run_backtest(Strategy.model_validate(SMA3_STRATEGY), bars, no_fee(1000))

    assert report.final_equity == pytest.approx(1000)
    assert report.total_return == pytest.approx(0)


def test_open_position_is_valued_at_last_close():
    # 第 4 天訊號，第 5 天開盤 10 買進 100 股，最後收盤 20 → 權益 2000
    bars = make_bars([(10, 10), (10, 10), (10, 10), (10, 13), (10, 20)])

    report = run_backtest(Strategy.model_validate(SMA3_STRATEGY), bars, no_fee(1000))

    assert report.final_equity == pytest.approx(2000)
    assert report.total_return == pytest.approx(1.0)


def test_signal_on_last_day_is_not_filled():
    # 最後一天才出現訊號，沒有下一個交易日可以成交
    bars = make_bars([(10, 10), (10, 10), (10, 10), (10, 13)])

    report = run_backtest(Strategy.model_validate(SMA3_STRATEGY), bars, no_fee(1000))

    assert report.final_equity == pytest.approx(1000)


def test_strategy_requires_supported_version():
    with pytest.raises(ValueError):
        Strategy.model_validate({**SMA3_STRATEGY, "version": 99})
