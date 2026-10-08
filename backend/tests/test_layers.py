"""層模型、出場比例與規則清單（#7，ADR 0007）：只透過 run_backtest 的輸入與輸出驗證。

測試都不收手續費、不計滑價；證交稅依法固定，只影響現金，不影響股數。
"""

from datetime import date, timedelta

import pytest

from backtest import BacktestSettings, Bar, Strategy, run_backtest

DAY1 = date(2021, 1, 4)

ALWAYS = {"type": "close_vs_value", "op": "above", "value": 0}


def day(n: int) -> date:
    return DAY1 + timedelta(days=n - 1)


def bars(*rows: tuple[float, float]) -> list[Bar]:
    """以 (開盤價, 收盤價) 建立從第 1 天起的日 K。"""
    return [
        Bar(
            date=day(i + 1),
            open=o,
            high=max(o, c),
            low=min(o, c),
            close=c,
            volume=1000,
        )
        for i, (o, c) in enumerate(rows)
    ]


def flat(*closes: float) -> list[Bar]:
    """開盤價等於收盤價的日 K。"""
    return bars(*((c, c) for c in closes))


def strategy(*rules: tuple[str, dict], entry=(0.5, 0.3, 0.2), exit_=(0.5, 0.3, 0.2)) -> Strategy:
    return Strategy.model_validate(
        {
            "version": 1,
            "entry_ratios": list(entry),
            "exit_ratios": list(exit_),
            "rules": [{"action": a, "condition": c} for a, c in rules],
        }
    )


def above(value: float) -> dict:
    return {"type": "close_vs_value", "op": "above", "value": value}


def below(value: float) -> dict:
    return {"type": "close_vs_value", "op": "below", "value": value}


def run(strat: Strategy, data: list[Bar], **overrides):
    values = {"initial_capital": 1000, "fee_discount": 0, "min_fee": 0, "slippage": 0}
    return run_backtest(strat, data, BacktestSettings(**(values | overrides)))


def summary(report) -> list[tuple[date, str, int, int]]:
    return [(t.date, t.action, t.shares, t.batch) for t in report.trades]


def test_entry_and_adds_fill_layers_by_entry_ratios_until_full():
    # 預計投入資金 1000：第 1 層 500 → 50 股、第 2 層 300 → 30 股、第 3 層 200 → 20 股
    # 三層都滿之後，加碼規則不再成交
    report = run(strategy(("entry", ALWAYS), ("add", ALWAYS)), flat(10, 10, 10, 10, 10, 10))

    assert summary(report) == [
        (day(2), "entry", 50, 1),
        (day(3), "add", 30, 2),
        (day(4), "add", 20, 3),
    ]


def test_only_first_applicable_matching_rule_runs_each_day():
    # 第 2 天收盤時，出場與加碼都成立；出場排在前面，所以只執行出場
    exit_first = strategy(("entry", ALWAYS), ("exit", below(100)), ("add", ALWAYS))
    add_first = strategy(("entry", ALWAYS), ("add", ALWAYS), ("exit", below(100)))

    assert summary(run(exit_first, flat(10, 10, 10)))[1][:2] == (day(3), "exit")
    assert summary(run(add_first, flat(10, 10, 10)))[1][:2] == (day(3), "add")


def test_exit_then_reduce_sell_batches_by_exit_ratios_of_shares_at_exit_start():
    # 單層買滿 100 股；出場開始時持股 100：依序賣 50、30、剩下的 20，之後空手再進場
    strat = strategy(("entry", ALWAYS), ("exit", below(100)), ("reduce", below(100)), entry=(1,))

    report = run(strat, flat(10, 10, 10, 10, 10, 10))

    assert summary(report) == [
        (day(2), "entry", 100, 1),
        (day(3), "exit", 50, 1),
        (day(4), "reduce", 30, 2),
        (day(5), "reduce", 20, 3),
        (day(6), "entry", 99, 1),  # 三批證交稅 1 + 0 + 0，現金 999 ÷ 10 = 99 股
    ]


def test_exit_batches_floor_and_last_batch_sells_everything_left():
    # 990 ÷ 10 = 99 股；99 × 50% = 49.5 → 49，99 × 30% = 29.7 → 29，最後一批賣剩下的 21
    strat = strategy(("entry", ALWAYS), ("exit", below(100)), ("reduce", below(100)), entry=(1,))

    report = run(strat, flat(10, 10, 10, 10, 10), initial_capital=990)

    assert [t.shares for t in report.trades] == [99, 49, 29, 21]


def test_reduce_does_not_apply_before_exit_starts():
    strat = strategy(("entry", ALWAYS), ("reduce", ALWAYS), entry=(1,))

    report = run(strat, flat(10, 10, 10, 10))

    assert [t.action for t in report.trades] == ["entry"]


def test_stop_loss_sells_everything_at_once():
    # 兩層各 50 股 @10，平均成本 10；第 3 天收盤 8 虧損 20% ≥ 10% → 第 4 天開盤全部賣出
    strat = strategy(
        ("stop_loss", {"type": "pnl_vs_avg_cost", "op": "loss", "pct": 0.1}),
        ("entry", ALWAYS),
        ("add", ALWAYS),
        entry=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 10), (10, 8), (8, 8)))

    assert summary(report) == [
        (day(2), "entry", 50, 1),
        (day(3), "add", 50, 2),
        (day(4), "stop_loss", 100, 1),
    ]


def test_take_profit_sells_next_exit_batch():
    # 買 100 股 @10；收盤 12 獲利 20% ≥ 10% → 依出場比例 50/50 分兩批賣出
    strat = strategy(
        ("take_profit", {"type": "pnl_vs_avg_cost", "op": "gain", "pct": 0.1}),
        ("entry", ALWAYS),
        entry=(1,),
        exit_=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 12), (12, 12), (12, 12)))

    assert summary(report) == [
        (day(2), "entry", 100, 1),
        (day(3), "take_profit", 50, 1),
        (day(4), "take_profit", 50, 2),
    ]


def test_selling_frees_a_layer_and_adding_restarts_exit_batches():
    # 第 2 天 第 1 層 500 → 50 股 @10，現金 500
    # 第 3 天 第 2 層 500 → 25 股 @20，現金 0（兩層都滿）
    # 第 4 天 出場第 1 批：基數 75 × 50% = 37 股 @4，現金 148，釋出第 2 層
    # 第 5 天 再加碼補回第 2 層：現金只有 148 → 7 股 @20
    # 第 6 天 加碼後出場重新從第 1 批算：基數 38 + 7 = 45 × 50% = 22 股
    strat = strategy(
        ("entry", ALWAYS),
        ("add", above(15)),
        ("exit", below(5)),
        ("reduce", below(5)),
        entry=(0.5, 0.5),
        exit_=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 20), (20, 4), (4, 20), (20, 4), (4, 4)))

    assert summary(report)[:5] == [
        (day(2), "entry", 50, 1),
        (day(3), "add", 25, 2),
        (day(4), "exit", 37, 1),
        (day(5), "add", 7, 2),
        (day(6), "exit", 22, 1),
    ]


def test_add_condition_compares_with_last_buy_price():
    # 第 2 天買進 @10；收盤 10.5 未達 +10%，第 3 天收盤 11 達到 → 第 4 天加碼
    strat = strategy(
        ("entry", ALWAYS),
        ("add", {"type": "price_vs_last_buy", "op": "up", "pct": 0.1}),
        entry=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 10.5), (10.5, 11), (11, 11)))

    assert [(t.date, t.action) for t in report.trades] == [(day(2), "entry"), (day(4), "add")]


def test_add_condition_can_average_down():
    strat = strategy(
        ("entry", ALWAYS),
        ("add", {"type": "price_vs_last_buy", "op": "down", "pct": 0.1}),
        entry=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 9.5), (9.5, 9), (9, 9)))

    assert [(t.date, t.action) for t in report.trades] == [(day(2), "entry"), (day(4), "add")]


def test_reduce_condition_compares_with_last_sell_price():
    # 第 3 天以 8 賣出第 1 批；收盤 8.5 未達 +10%（8.8），第 4 天收盤 9 達到 → 第 5 天減碼
    strat = strategy(
        ("entry", ALWAYS),
        ("exit", below(9)),
        ("reduce", {"type": "price_vs_last_sell", "op": "up", "pct": 0.1}),
        entry=(1,),
        exit_=(0.5, 0.5),
    )

    report = run(strat, bars((10, 10), (10, 8), (8, 8.5), (8.5, 9), (9, 9)))

    assert [(t.date, t.action) for t in report.trades] == [
        (day(2), "entry"),
        (day(3), "exit"),
        (day(5), "reduce"),
    ]


def test_new_position_uses_all_cash_as_planned_capital():
    # 第一段持倉：第 1 層 500 → 50 股 @10，現金 500；賣出 50 股 @20 = 1000，證交稅 3 → 現金 1497
    # 第二段持倉：預計投入資金 1497，第 1 層 748.5 → 37 股 @20
    strat = strategy(("entry", above(15)), ("exit", below(100)), entry=(0.5, 0.5), exit_=(1,))

    report = run(strat, bars((20, 20), (10, 20), (20, 20), (20, 20)))

    assert summary(report) == [
        (day(2), "entry", 50, 1),
        (day(3), "exit", 50, 1),
        (day(4), "entry", 37, 1),
    ]


def test_board_lot_layers_round_down_to_whole_lots():
    # 預計投入資金 250000 × 50% = 125000 ÷ 100 = 1250 股 → 整張 1000 股
    strat = strategy(("entry", ALWAYS), entry=(0.5, 0.5))

    report = run(strat, flat(100, 100), initial_capital=250_000, lot="board")

    assert report.trades[0].shares == 1000


def test_conditions_can_be_nested_groups():
    # (收盤 > 15 且 收盤 < 25) 或 收盤 < 5
    condition = {
        "type": "any",
        "conditions": [
            {"type": "all", "conditions": [above(15), below(25)]},
            below(5),
        ],
    }
    strat = strategy(("entry", condition), entry=(1,))

    assert run(strat, flat(10, 10)).trades == []
    assert run(strat, flat(20, 20)).trades[0].date == day(2)
    assert run(strat, flat(30, 30)).trades == []
    assert run(strat, flat(4, 4)).trades[0].date == day(2)


@pytest.mark.parametrize(
    "ratios",
    [(), (0.5, 0.3), (0.5, 0.6), (1.0, 0.0), (0.2,) * 6],
)
def test_ratios_must_be_positive_sum_to_one_and_have_one_to_five_batches(ratios):
    with pytest.raises(ValueError):
        strategy(("entry", ALWAYS), entry=ratios)
    with pytest.raises(ValueError):
        strategy(("entry", ALWAYS), exit_=ratios)


def test_ratios_default_to_50_30_20():
    strat = Strategy.model_validate(
        {"version": 1, "rules": [{"action": "entry", "condition": ALWAYS}]}
    )

    assert strat.entry_ratios == [0.5, 0.3, 0.2]
    assert strat.exit_ratios == [0.5, 0.3, 0.2]


def test_add_that_cannot_afford_one_unit_does_not_block_lower_rules():
    # 第 1 層 500 → 50 股 @10，之後收盤漲到 600，剩下的現金 500 買不起 1 股
    # 加碼排在出場前面，但買不起時視為不適用，所以出場仍會執行
    strat = strategy(
        ("entry", ALWAYS),
        ("add", ALWAYS),
        ("exit", below(1000)),
        entry=(0.5, 0.5),
        exit_=(1,),
    )

    report = run(strat, bars((10, 10), (10, 600), (600, 600)))

    assert [(t.date, t.action) for t in report.trades] == [(day(2), "entry"), (day(3), "exit")]
