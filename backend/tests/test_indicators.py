"""技術指標條件積木（#10）：只透過 run_backtest 的輸入與輸出驗證。

每個測試都只有一條進場規則；條件第一次成立的那天收盤後產生訊號，
下一個交易日開盤成交，所以斷言「第一筆成交的日期」即可知道條件哪天成立。
"""

from datetime import date, timedelta

import pytest

from backtest import BacktestSettings, Bar, Strategy, run_backtest

DAY1 = date(2021, 1, 4)


def day(n: int) -> date:
    return DAY1 + timedelta(days=n - 1)


def make_bars(closes, highs=None, lows=None, volumes=None) -> list[Bar]:
    n = len(closes)
    highs = highs or closes
    lows = lows or closes
    volumes = volumes or [1000] * n
    return [
        Bar(
            date=day(i + 1),
            open=closes[i],
            high=highs[i],
            low=lows[i],
            close=closes[i],
            volume=volumes[i],
        )
        for i in range(n)
    ]


def first_entry_day(condition: dict, data: list[Bar]) -> date | None:
    strategy = Strategy.model_validate(
        {
            "version": 1,
            "entry_ratios": [1],
            "exit_ratios": [1],
            "rules": [{"action": "entry", "condition": condition}],
        }
    )
    settings = BacktestSettings(initial_capital=1000, fee_discount=0, min_fee=0, slippage=0)
    trades = run_backtest(strategy, data, settings).trades
    return trades[0].date if trades else None


# --- 均線交叉 -------------------------------------------------------------


def test_sma_golden_cross():
    # 2 日線 vs 3 日線：第 4 天 9.5 < 9.67；第 5 天 10.5 > 10.33 → 黃金交叉，第 6 天成交
    data = make_bars([10, 10, 10, 9, 12, 12])

    cond = {"type": "sma_cross", "op": "golden", "fast": 2, "slow": 3}
    assert first_entry_day(cond, data) == day(6)


def test_sma_death_cross():
    # 第 4 天 2 日線 10.5 > 3 日線 10.33；第 5 天 9.5 < 9.67 → 死亡交叉
    data = make_bars([10, 10, 10, 11, 8, 8])

    cond = {"type": "sma_cross", "op": "death", "fast": 2, "slow": 3}
    assert first_entry_day(cond, data) == day(6)


def test_sma_cross_requires_fast_shorter_than_slow():
    with pytest.raises(ValueError):
        first_entry_day({"type": "sma_cross", "op": "golden", "fast": 5, "slow": 5}, [])


# --- RSI（Wilder 平滑） ----------------------------------------------------


def test_rsi_uses_wilder_smoothing():
    # 2 日 RSI：漲跌 +1、+1 → 第 3 天 RSI 100；第 4 天跌 1：
    # 平均漲幅 (1 + 0) / 2 = 0.5，平均跌幅 (0 + 1) / 2 = 0.5 → RSI 50
    data = make_bars([10, 11, 12, 11, 11])

    assert first_entry_day({"type": "rsi", "period": 2, "op": "below", "value": 60}, data) == day(5)
    assert first_entry_day({"type": "rsi", "period": 2, "op": "above", "value": 99}, data) == day(4)


def test_rsi_is_undefined_before_enough_bars():
    data = make_bars([10, 11])

    assert first_entry_day({"type": "rsi", "period": 2, "op": "above", "value": 0}, data) is None


# --- MACD -----------------------------------------------------------------


def test_macd_golden_cross():
    # EMA 以第一天收盤價為起點，平滑係數 2 / (N + 1)
    # 快線 EMA1 = 收盤價；慢線 EMA2：10、10、10、8、11.33
    # DIF = 0、0、0、-1、1.67；訊號線 EMA2(DIF) = 0、0、0、-0.67、0.89
    # 第 4 天 DIF < 訊號線，第 5 天 DIF > 訊號線 → 黃金交叉
    data = make_bars([10, 10, 10, 7, 13, 13])

    cond = {"type": "macd_cross", "op": "golden", "fast": 1, "slow": 2, "signal": 2}
    assert first_entry_day(cond, data) == day(6)


def test_macd_death_cross():
    data = make_bars([10, 10, 10, 13, 7, 7])

    cond = {"type": "macd_cross", "op": "death", "fast": 1, "slow": 2, "signal": 2}
    assert first_entry_day(cond, data) == day(6)


# --- KD（台灣常用：RSV、K、D 以 1/3 平滑，起始 50） --------------------------


KD_DATA = [10, 12, 11, 13, 13]
# 2 日 KD：
# 第 2 天 RSV 100 → K 66.67、D 55.56
# 第 3 天 RSV 0   → K 44.44、D 51.85（K 跌破 D：死亡交叉）
# 第 4 天 RSV 100 → K 62.96、D 55.56（K 突破 D：黃金交叉）


def test_kd_golden_cross():
    cond = {"type": "kd_cross", "op": "golden", "period": 2}
    assert first_entry_day(cond, make_bars(KD_DATA)) == day(5)


def test_kd_death_cross():
    cond = {"type": "kd_cross", "op": "death", "period": 2}
    assert first_entry_day(cond, make_bars(KD_DATA)) == day(4)


def test_kd_level():
    k_above = {"type": "kd_level", "line": "k", "op": "above", "value": 60, "period": 2}
    d_above = {"type": "kd_level", "line": "d", "op": "above", "value": 55, "period": 2}
    k_below = {"type": "kd_level", "line": "k", "op": "below", "value": 50, "period": 2}

    assert first_entry_day(k_above, make_bars(KD_DATA)) == day(3)
    assert first_entry_day(d_above, make_bars(KD_DATA)) == day(3)
    assert first_entry_day(k_below, make_bars(KD_DATA)) == day(4)


def test_kd_uses_high_and_low():
    # 第 2 天：最高 14、最低 9（兩天之內），收盤 12 → RSV = (12 - 9) / (14 - 9) = 60
    # K = 50 × 2/3 + 60/3 = 53.33
    data = make_bars([10, 12, 12], highs=[11, 14, 12], lows=[9, 11, 12])

    above = {"type": "kd_level", "line": "k", "op": "above", "value": 53, "period": 2}
    below = {"type": "kd_level", "line": "k", "op": "below", "value": 53.4, "period": 2}
    assert first_entry_day(above, data) == day(3)
    assert first_entry_day(below, data) == day(3)


# --- 布林通道 --------------------------------------------------------------


def test_bollinger_upper_and_lower_band():
    # 3 日、1 倍標準差（母體標準差）：10、10、13 → 平均 11、標準差 √2 ≈ 1.414
    # 上軌 12.41，收盤 13 突破上軌
    up = make_bars([10, 10, 13, 13])
    down = make_bars([10, 10, 7, 7])

    above = {"type": "bollinger", "op": "above_upper", "period": 3, "std": 1}
    below = {"type": "bollinger", "op": "below_lower", "period": 3, "std": 1}
    assert first_entry_day(above, up) == day(4)
    assert first_entry_day(below, up) is None
    assert first_entry_day(below, down) == day(4)


# --- 成交量 ----------------------------------------------------------------


def test_volume_compared_with_average_of_previous_days():
    # 第 4 天成交量 400，前 3 天平均 100 → 400 > 100 × 2
    data = make_bars([10] * 5, volumes=[100, 100, 100, 400, 100])

    above = {"type": "volume_vs_avg", "op": "above", "period": 3, "multiple": 2}
    below = {"type": "volume_vs_avg", "op": "below", "period": 3, "multiple": 0.5}
    assert first_entry_day(above, data) == day(5)
    assert first_entry_day(below, data) is None
