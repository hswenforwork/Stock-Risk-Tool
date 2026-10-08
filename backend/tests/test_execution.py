"""成交規則與交易成本（#6）：只透過 run_backtest 的輸入與輸出驗證。

共用行情：收盤 10、10、10、13 → 第 4 天收盤站上 3 日均線（11），產生進場訊號；
第 6 天收盤 9 跌破 3 日均線（約 11.33），產生出場訊號。成交都在下一個交易日開盤。
"""

from datetime import date, timedelta

import pytest

from backtest import BacktestSettings, Bar, Strategy, run_backtest

STRATEGY = Strategy.model_validate(
    {
        "version": 1,
        "rules": [
            {"action": "entry", "condition": {"type": "close_vs_sma", "op": "above", "period": 3}},
            {"action": "exit", "condition": {"type": "close_vs_sma", "op": "below", "period": 3}},
        ],
    }
)

DAY1 = date(2021, 1, 4)


def day(n: int) -> date:
    return DAY1 + timedelta(days=n - 1)


def bar(n: int, open_: float, close: float) -> Bar:
    return Bar(
        date=day(n),
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        volume=1000,
    )


def round_trip(entry_open: float, exit_open: float) -> list[Bar]:
    """第 5 天開盤以 entry_open 進場、第 7 天開盤以 exit_open 出場的 7 天行情。"""
    return [
        bar(1, 10, 10),
        bar(2, 10, 10),
        bar(3, 10, 10),
        bar(4, 10, 13),
        bar(5, entry_open, 12),
        bar(6, 12, 9),
        bar(7, exit_open, exit_open),
    ]


def settings(**overrides) -> BacktestSettings:
    """預設不收手續費、不計滑價，個別測試再覆寫要驗證的項目。"""
    values = {"initial_capital": 1000, "fee_discount": 0, "min_fee": 0, "slippage": 0}
    return BacktestSettings(**(values | overrides))


def test_default_costs_round_trip():
    # 預設：手續費 0.1425% × 6 折 = 0.0855%、最低 1 元，滑價 0.1%，股票證交稅 0.3%
    # 買進價 100 × 1.001 = 100.1，股數 floor(10000 ÷ (100.1 × 1.000855)) = 99
    #   金額 9909.9，手續費 floor(8.47) = 8，剩餘現金 10000 - 9909.9 - 8 = 82.1
    # 賣出價 110 × 0.999 = 109.89，金額 99 × 109.89 = 10879.11
    #   手續費 floor(9.30) = 9，證交稅 floor(32.64) = 32
    # 權益 82.1 + 10879.11 - 9 - 32 = 10920.21
    report = run_backtest(STRATEGY, round_trip(100, 110), BacktestSettings(initial_capital=10_000))

    entry, exit_ = report.trades
    assert (entry.date, entry.action, entry.shares) == (day(5), "entry", 99)
    assert entry.price == pytest.approx(100.1)
    assert (entry.fee, entry.tax) == (8, 0)
    assert (exit_.date, exit_.action, exit_.shares) == (day(7), "exit", 99)
    assert exit_.price == pytest.approx(109.89)
    assert (exit_.fee, exit_.tax) == (9, 32)
    assert report.final_equity == pytest.approx(10920.21)


def test_fee_has_minimum():
    # 金額 99 × 10 = 990，手續費 floor(990 × 0.0855%) = 0，低於最低 1 元 → 收 1 元
    report = run_backtest(STRATEGY, round_trip(10, 10), settings(fee_discount=0.6, min_fee=1))

    assert report.trades[0].shares == 99
    assert report.trades[0].fee == 1


def test_fee_reduces_affordable_shares():
    # 100 股要 10000 + 手續費 14 > 10000，所以只能買 99 股
    report = run_backtest(
        STRATEGY, round_trip(100, 100), settings(initial_capital=10_000, fee_discount=1)
    )

    assert report.trades[0].shares == 99


def test_odd_lot_shares_are_floored():
    # 1000 ÷ 30 = 33.3 → 33 股，剩 10 元留在現金
    report = run_backtest(STRATEGY, round_trip(30, 30), settings())

    assert report.trades[0].shares == 33
    assert report.final_equity == pytest.approx(10 + 33 * 30 - 2)  # 賣出證交稅 floor(2.97) = 2


def test_board_lot_buys_whole_lots_only():
    # 250000 ÷ 100 = 2500 股 → 整張只能買 2000 股
    report = run_backtest(
        STRATEGY, round_trip(100, 100), settings(initial_capital=250_000, lot="board")
    )

    assert report.trades[0].shares == 2000


def test_board_lot_skips_entry_when_cash_is_short_of_one_lot():
    report = run_backtest(STRATEGY, round_trip(100, 100), settings(lot="board"))

    assert report.trades == []
    assert report.final_equity == pytest.approx(1000)


@pytest.mark.parametrize(("is_etf", "tax"), [(False, 6), (True, 2)])
def test_securities_tax_depends_on_security_type(is_etf, tax):
    # 買 100 股 @10，賣 100 股 @20 = 2000；股票 0.3% → 6，ETF 0.1% → 2
    report = run_backtest(STRATEGY, round_trip(10, 20), settings(is_etf=is_etf))

    assert report.trades[0].tax == 0
    assert report.trades[1].tax == tax
    assert report.final_equity == pytest.approx(2000 - tax)


def test_signal_is_delayed_past_suspended_days():
    # 第 5 天停牌（close = 0），第 4 天的進場訊號延到第 6 天開盤成交
    bars = [
        bar(1, 10, 10),
        bar(2, 10, 10),
        bar(3, 10, 10),
        bar(4, 10, 13),
        bar(5, 0, 0),
        bar(6, 20, 14),
    ]

    report = run_backtest(STRATEGY, bars, settings())

    (entry,) = report.trades
    assert entry.date == day(6)
    assert entry.price == pytest.approx(20)
    assert entry.delayed is True


def test_trades_are_not_delayed_on_normal_days():
    report = run_backtest(STRATEGY, round_trip(10, 10), settings())

    assert [t.delayed for t in report.trades] == [False, False]


def test_bars_before_start_date_only_warm_up_indicators():
    # 起始日為第 5 天：第 4 天的訊號不算；第 5 天收盤 12 仍站上均線（用第 3–5 天計算），
    # 所以第 6 天開盤才進場
    report = run_backtest(STRATEGY, round_trip(10, 10), settings(start_date=day(5)))

    assert report.trades[0].date == day(6)


def test_end_date_stops_backtest_and_values_position_at_its_close():
    # 第 5 天開盤以 10 買進 100 股，回測在第 5 天結束，以當天收盤 12 計值
    report = run_backtest(STRATEGY, round_trip(10, 10), settings(end_date=day(5)))

    assert len(report.trades) == 1
    assert report.final_equity == pytest.approx(1200)


def test_start_date_cannot_be_before_odd_lot_intraday_trading():
    # 盤中零股交易 2020-10-26 才開放（ADR 0005）
    with pytest.raises(ValueError):
        settings(start_date=date(2020, 10, 23))


def test_end_date_cannot_be_before_start_date():
    with pytest.raises(ValueError):
        settings(start_date=date(2021, 3, 1), end_date=date(2021, 2, 1))
