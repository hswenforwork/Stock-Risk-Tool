"""技術指標序列。

每個函式都回傳和輸入等長的序列，第 i 個值只用到第 0..i 天的資料（不偷看未來）；
資料不足時為 None。
"""

import math
from collections.abc import Sequence

Series = list[float | None]


def sma(values: Sequence[float], period: int) -> Series:
    out: Series = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= period:
            total -= values[i - period]
        if i >= period - 1:
            out[i] = total / period
    return out


def ema(values: Sequence[float], period: int) -> list[float]:
    """指數移動平均：以第一個值為起點，平滑係數 2 / (N + 1)。"""
    alpha = 2 / (period + 1)
    out: list[float] = []
    for v in values:
        out.append(v if not out else out[-1] + alpha * (v - out[-1]))
    return out


def rsi(closes: Sequence[float], period: int) -> Series:
    """RSI（Wilder 平滑）：第一個平均為前 N 個漲跌的簡單平均，之後 (前值 × (N-1) + 本期) / N。"""
    out: Series = [None] * len(closes)
    avg_gain = avg_loss = 0.0
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain, loss = max(change, 0.0), max(-change, 0.0)
        if i <= period:
            avg_gain += gain / period
            avg_loss += loss / period
            if i < period:
                continue
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def macd(closes: Sequence[float], fast: int, slow: int, signal: int) -> tuple[Series, Series]:
    """回傳 (DIF, 訊號線)；前 slow + signal - 2 天視為暖機，值為 None。"""
    fast_ema, slow_ema = ema(closes, fast), ema(closes, slow)
    dif = [f - s for f, s in zip(fast_ema, slow_ema, strict=True)]
    dem = ema(dif, signal)
    warmup = slow + signal - 2
    return (
        [v if i >= warmup else None for i, v in enumerate(dif)],
        [v if i >= warmup else None for i, v in enumerate(dem)],
    )


def kd(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int
) -> tuple[Series, Series]:
    """台灣常用的 KD：RSV = (收盤 - N 日最低) / (N 日最高 - N 日最低) × 100，
    K = 前 K × 2/3 + RSV / 3，D = 前 D × 2/3 + K / 3，K、D 起始值 50。
    N 日最高等於最低時，RSV 取 50。
    """
    k_out: Series = [None] * len(closes)
    d_out: Series = [None] * len(closes)
    k = d = 50.0
    for i in range(period - 1, len(closes)):
        high = max(highs[i - period + 1 : i + 1])
        low = min(lows[i - period + 1 : i + 1])
        rsv = 50.0 if high == low else (closes[i] - low) / (high - low) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
        k_out[i], d_out[i] = k, d
    return k_out, d_out


def bollinger(closes: Sequence[float], period: int, width: float) -> tuple[Series, Series]:
    """回傳 (上軌, 下軌) = N 日均線 ± width × N 日母體標準差。"""
    upper: Series = [None] * len(closes)
    lower: Series = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = sum(window) / period
        std = math.sqrt(sum((v - mean) ** 2 for v in window) / period)
        upper[i], lower[i] = mean + width * std, mean - width * std
    return upper, lower


def previous_average(values: Sequence[float], period: int) -> Series:
    """前 N 天（不含當天）的平均。"""
    out: Series = [None] * len(values)
    for i in range(period, len(values)):
        out[i] = sum(values[i - period : i]) / period
    return out
