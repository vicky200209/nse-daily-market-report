"""Candlestick pattern detection + a stateless 'pattern tracker' that measures
what really happened after each pattern in the past year of data."""
import pandas as pd

# name -> (bias, number of candles, plain-English meaning)
PATTERNS = {
    "Doji": ("neutral", 1, "Open and close almost equal - buyers and sellers are in a tie. Shows indecision; often comes before a change in direction."),
    "Dragonfly Doji": ("bullish", 1, "Sellers pushed price far down but buyers brought it all the way back up to the open. Bullish when it appears after a fall."),
    "Gravestone Doji": ("bearish", 1, "Buyers pushed price far up but sellers brought it all the way back down to the open. Bearish when it appears after a rise."),
    "Hammer": ("bullish", 1, "Small body at the top, long lower wick, after a fall. Sellers tried to push down but buyers fought back - a possible bottom."),
    "Hanging Man": ("bearish", 1, "Same shape as a hammer but after a rise. Warns that sellers are starting to appear - a possible top."),
    "Inverted Hammer": ("bullish", 1, "Small body at the bottom, long upper wick, after a fall. Buyers are testing higher prices - a possible bottom if the next candle confirms."),
    "Shooting Star": ("bearish", 1, "Small body at the bottom, long upper wick, after a rise. Buyers pushed up but were rejected - a possible top."),
    "Bullish Marubozu": ("bullish", 1, "Big green candle with almost no wicks - buyers were in control from open to close."),
    "Bearish Marubozu": ("bearish", 1, "Big red candle with almost no wicks - sellers were in control from open to close."),
    "Spinning Top": ("neutral", 1, "Small body with wicks on both sides - neither side won the day. Indecision."),
    "Bullish Engulfing": ("bullish", 2, "A green candle whose body completely covers the previous red body. Buyers overpowered sellers - a possible reversal up."),
    "Bearish Engulfing": ("bearish", 2, "A red candle whose body completely covers the previous green body. Sellers overpowered buyers - a possible reversal down."),
    "Bullish Harami": ("bullish", 2, "A small green candle inside the previous big red body. Selling is slowing down ('harami' = pregnant in Japanese)."),
    "Bearish Harami": ("bearish", 2, "A small red candle inside the previous big green body. Buying is slowing down."),
    "Piercing Line": ("bullish", 2, "After a red candle, a green candle opens lower but closes above the middle of the red body. Buyers stepping in."),
    "Dark Cloud Cover": ("bearish", 2, "After a green candle, a red candle opens higher but closes below the middle of the green body. Sellers stepping in."),
    "Tweezer Bottom": ("bullish", 2, "Two candles with almost the same low after a fall - price was rejected twice at the same floor (support)."),
    "Tweezer Top": ("bearish", 2, "Two candles with almost the same high after a rise - price was rejected twice at the same ceiling (resistance)."),
    "Morning Star": ("bullish", 3, "Big red candle, then a small 'star' candle, then a big green candle. A classic 3-candle bottom reversal."),
    "Evening Star": ("bearish", 3, "Big green candle, then a small 'star' candle, then a big red candle. A classic 3-candle top reversal."),
    "Three White Soldiers": ("bullish", 3, "Three strong green candles in a row, each closing higher. Steady buying pressure."),
    "Three Black Crows": ("bearish", 3, "Three strong red candles in a row, each closing lower. Steady selling pressure."),
}


def _parts(r):
    o, h, l, c = r["Open"], r["High"], r["Low"], r["Close"]
    body = abs(c - o)
    rng = max(h - l, 1e-9)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return o, h, l, c, body, rng, upper, lower


def detect_at(df: pd.DataFrame, i: int) -> list[str]:
    """Return pattern names that complete on candle i (positional index)."""
    if i < 5:
        return []
    found = []
    r, p, pp = df.iloc[i], df.iloc[i - 1], df.iloc[i - 2]
    o, h, l, c, body, rng, up, lo = _parts(r)
    avg_body = (df["Close"] - df["Open"]).abs().iloc[max(0, i - 20):i].mean() or body
    # trend context: compare with close 5 sessions ago
    prior_down = df["Close"].iloc[i - 1] < df["Close"].iloc[i - 6]
    prior_up = df["Close"].iloc[i - 1] > df["Close"].iloc[i - 6]
    green, red = c > o, c < o

    # --- single candle ---
    if body <= 0.1 * rng:
        if lo >= 0.6 * rng and up <= 0.1 * rng:
            found.append("Dragonfly Doji")
        elif up >= 0.6 * rng and lo <= 0.1 * rng:
            found.append("Gravestone Doji")
        else:
            found.append("Doji")
    elif lo >= 2 * body and up <= 0.3 * body and body < 0.4 * rng:
        if prior_down:
            found.append("Hammer")
        elif prior_up:
            found.append("Hanging Man")
    elif up >= 2 * body and lo <= 0.3 * body and body < 0.4 * rng:
        if prior_down:
            found.append("Inverted Hammer")
        elif prior_up:
            found.append("Shooting Star")
    elif body >= 0.9 * rng and body > 1.3 * avg_body:
        found.append("Bullish Marubozu" if green else "Bearish Marubozu")
    elif body <= 0.3 * rng and up > body and lo > body:
        found.append("Spinning Top")

    # --- two candle ---
    po, ph, pl, pc, pbody, prng, _, _ = _parts(p)
    p_green, p_red = pc > po, pc < po
    if p_red and green and o <= pc and c >= po and body > pbody:
        found.append("Bullish Engulfing")
    elif p_green and red and o >= pc and c <= po and body > pbody:
        found.append("Bearish Engulfing")
    elif p_red and green and pbody > avg_body and max(o, c) < po and min(o, c) > pc:
        found.append("Bullish Harami")
    elif p_green and red and pbody > avg_body and max(o, c) < pc and min(o, c) > po:
        found.append("Bearish Harami")
    elif p_red and green and prior_down and o < pc and c > (po + pc) / 2 and c < po:
        found.append("Piercing Line")
    elif p_green and red and prior_up and o > pc and c < (po + pc) / 2 and c > po:
        found.append("Dark Cloud Cover")
    tol = 0.002 * c
    if prior_down and abs(l - pl) <= tol and p_red and green:
        found.append("Tweezer Bottom")
    if prior_up and abs(h - ph) <= tol and p_green and red:
        found.append("Tweezer Top")

    # --- three candle ---
    a, b = pp, p
    ao, _, _, ac, abody, _, _, _ = _parts(a)
    bo, _, _, bc, bbody, _, _, _ = _parts(b)
    if ac < ao and abody > avg_body and bbody < 0.5 * abody and green and c > (ao + ac) / 2 and prior_down:
        found.append("Morning Star")
    if ac > ao and abody > avg_body and bbody < 0.5 * abody and red and c < (ao + ac) / 2 and prior_up:
        found.append("Evening Star")
    three = df.iloc[i - 2:i + 1]
    if all(three["Close"] > three["Open"]) and three["Close"].is_monotonic_increasing and \
            all((three["Close"] - three["Open"]) > 0.6 * avg_body) and all(three["High"] - three["Close"] < 0.3 * (three["High"] - three["Low"])):
        found.append("Three White Soldiers")
    if all(three["Close"] < three["Open"]) and three["Close"].is_monotonic_decreasing and \
            all((three["Open"] - three["Close"]) > 0.6 * avg_body) and all(three["Close"] - three["Low"] < 0.3 * (three["High"] - three["Low"])):
        found.append("Three Black Crows")
    return found


def recent_patterns(df: pd.DataFrame, days: int = 5) -> list[dict]:
    out = []
    n = len(df)
    for i in range(max(0, n - days), n):
        for name in detect_at(df, i):
            out.append({"date": df.index[i].strftime("%d %b"), "days_ago": n - 1 - i, "pattern": name,
                        "bias": PATTERNS[name][0], "meaning": PATTERNS[name][2]})
    return out


def forward_outcomes(df: pd.DataFrame, horizons=(1, 3, 5)) -> list[dict]:
    """Every pattern in history (excluding the most recent 5 candles) with forward returns."""
    rows = []
    closes = df["Close"].values
    n = len(df)
    for i in range(5, n - max(horizons)):
        for name in detect_at(df, i):
            row = {"pattern": name, "bias": PATTERNS[name][0]}
            for hzn in horizons:
                row[f"ret{hzn}"] = (closes[i + hzn] / closes[i] - 1) * 100
            rows.append(row)
    return rows


def tracker_table(all_rows: list[dict]) -> list[dict]:
    """Aggregate outcomes: for bullish patterns success = price higher after N days; bearish = lower."""
    if not all_rows:
        return []
    d = pd.DataFrame(all_rows)
    out = []
    for name, g in d.groupby("pattern"):
        bias = g["bias"].iloc[0]
        rec = {"pattern": name, "bias": bias, "count": len(g)}
        for h in (1, 3, 5):
            r = g[f"ret{h}"]
            if bias == "bullish":
                rec[f"win{h}"] = round((r > 0).mean() * 100)
            elif bias == "bearish":
                rec[f"win{h}"] = round((r < 0).mean() * 100)
            else:
                rec[f"win{h}"] = None
            rec[f"avg{h}"] = round(r.mean(), 2)
        out.append(rec)
    order = {"bullish": 0, "bearish": 1, "neutral": 2}
    return sorted(out, key=lambda x: (order[x["bias"]], -x["count"]))
