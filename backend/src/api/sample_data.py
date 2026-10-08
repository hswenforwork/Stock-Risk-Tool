"""暫時寫死的策略與行情，等資料同步（#5）與策略編輯器（#10）完成後移除。"""

import math
from datetime import date, timedelta

from backtest import Bar, Strategy

SAMPLE_STRATEGY = Strategy.model_validate(
    {
        "version": 1,
        "entry_ratios": [0.5, 0.3, 0.2],
        "exit_ratios": [0.5, 0.5],
        "rules": [
            {
                "action": "stop_loss",
                "condition": {"type": "pnl_vs_avg_cost", "op": "loss", "pct": 0.08},
            },
            {"action": "exit", "condition": {"type": "close_vs_sma", "op": "below", "period": 20}},
            {
                "action": "reduce",
                "condition": {"type": "price_vs_last_sell", "op": "down", "pct": 0.03},
            },
            {"action": "add", "condition": {"type": "price_vs_last_buy", "op": "up", "pct": 0.03}},
            {"action": "entry", "condition": {"type": "close_vs_sma", "op": "above", "period": 20}},
        ],
    }
)


def _sample_bars() -> list[Bar]:
    """約一年、帶趨勢與波動的合成日 K（只有交易日，週末略過）。"""
    bars: list[Bar] = []
    day = date(2021, 1, 4)
    prev_close = 500.0
    i = 0
    while len(bars) < 250:
        if day.weekday() < 5:
            close = round(500 + i * 0.4 + 30 * math.sin(i / 12), 2)
            open_ = round((prev_close + close) / 2, 2)
            bars.append(
                Bar(
                    date=day,
                    open=open_,
                    high=max(open_, close) + 2,
                    low=min(open_, close) - 2,
                    close=close,
                    volume=10_000,
                )
            )
            prev_close = close
            i += 1
        day += timedelta(days=1)
    return bars


SAMPLE_BARS = _sample_bars()
