"""Technical indicators computed with plain pandas (no TA-Lib needed)."""
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series):
    line = ema(close, 12) - ema(close, 26)
    signal = ema(line, 9)
    return line, signal, line - signal


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(), (df["Low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def vwap(intraday: pd.DataFrame) -> pd.Series:
    tp = (intraday["High"] + intraday["Low"] + intraday["Close"]) / 3
    return (tp * intraday["Volume"]).cumsum() / intraday["Volume"].cumsum().replace(0, np.nan)


def support_resistance(df: pd.DataFrame, lookback: int = 120, window: int = 5):
    """Swing highs/lows over the lookback; return nearest support below and resistance above the last close."""
    d = df.tail(lookback)
    highs, lows = d["High"], d["Low"]
    piv_hi = highs[(highs == highs.rolling(2 * window + 1, center=True).max())].dropna()
    piv_lo = lows[(lows == lows.rolling(2 * window + 1, center=True).min())].dropna()
    last = float(df["Close"].iloc[-1])
    res = sorted([float(x) for x in piv_hi if x > last * 1.002])
    sup = sorted([float(x) for x in piv_lo if x < last * 0.998], reverse=True)
    # fall back to recent range extremes
    resistance = res[0] if res else float(d["High"].max())
    support = sup[0] if sup else float(d["Low"].min())
    return round(support, 2), round(resistance, 2)


def trend_label(close: float, s20: float, s50: float, s200: float) -> str:
    if any(pd.isna(x) for x in (s20, s50)):
        return "Not enough data"
    if close > s20 > s50 and (pd.isna(s200) or s50 > s200):
        return "Strong uptrend"
    if close > s50 and s20 > s50:
        return "Uptrend"
    if close < s20 < s50 and (pd.isna(s200) or s50 < s200):
        return "Strong downtrend"
    if close < s50 and s20 < s50:
        return "Downtrend"
    return "Sideways / mixed"


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    df["SMA20"], df["SMA50"], df["SMA200"] = sma(c, 20), sma(c, 50), sma(c, 200)
    df["RSI14"] = rsi(c)
    df["MACD"], df["MACDsig"], df["MACDhist"] = macd(c)
    df["ATR14"] = atr(df)
    df["VolAvg20"] = df["Volume"].rolling(20).mean()
    return df
