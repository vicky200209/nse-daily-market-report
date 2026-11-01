"""Rule-based beginner explanations written in Python (zero AI tokens).

Claude only writes what needs judgement (headline, market story, lesson, why-it-moved).
Everything here is generated from the numbers; anything Claude writes in narrative.json overrides it.
"""


def rs(v, d=2):
    return f"Rs {v:,.{d}f}"


def _chart_reading(s):
    p, it = s["price"], s["intraday"]
    rng = p["high"] - p["low"]
    pos = (p["close"] - p["low"]) / rng if rng else 0.5
    if pos >= 0.8:
        where = "near the day's high - buyers stayed in control until the end"
    elif pos <= 0.2:
        where = "near the day's low - sellers stayed in control until the end"
    else:
        where = "in the middle of the day's range - neither side clearly won"
    g = p["gap_pct"]
    if abs(g) < 0.15:
        opened = f"opened flat at {rs(p['open'])}"
    else:
        opened = (f"opened at {rs(p['open'])}, a **gap {'up' if g > 0 else 'down'}** of {abs(g):.2f}% "
                  "(the open differs from yesterday's close)")
    if p["close"] > it["or_high"]:
        orr = f"above the **opening range** (high-low of the first 15 minutes, {it['or_low']:,}-{it['or_high']:,}), a sign of strength"
    elif p["close"] < it["or_low"]:
        orr = f"below the **opening range** (high-low of the first 15 minutes, {it['or_low']:,}-{it['or_high']:,}), a sign of weakness"
    else:
        orr = f"inside the **opening range** (high-low of the first 15 minutes, {it['or_low']:,}-{it['or_high']:,})"
    return (f"{s['name']} {opened}. The day low ({rs(p['low'])}) came at {it['low_time']} and the high ({rs(p['high'])}) at {it['high_time']}. "
            f"It closed at {rs(p['close'])}, {where}; the close is {orr}. It finished {it['close_vs_vwap']} **VWAP** "
            f"(the day's average traded price, {rs(it['vwap_close'])}). Biggest 5-minute move: {it['biggest_5m_move']}.")


def _pattern_lesson(s):
    pats = s["patterns"]
    if not pats:
        return "No clear candlestick pattern formed in the last 5 days, so today's story comes from the trend and the support/resistance levels."
    non = [x for x in pats if x["bias"] != "neutral"]
    x = (non or pats)[-1]
    trend = s["tech"]["trend"].lower()
    txt = f"A **{x['pattern']}** ({x['bias']}) formed on {x['date']}. {x['history']}."
    if x["bias"] == "bullish" and "down" in trend:
        txt += f" The bigger trend is {trend}, and bullish patterns inside a downtrend are weaker - the trend is usually the stronger force."
    elif x["bias"] == "bearish" and "up" in trend:
        txt += f" The bigger trend is {trend}, and bearish patterns inside an uptrend are weaker - the trend is usually the stronger force."
    elif x["bias"] == "neutral":
        txt += " Neutral patterns only show indecision - wait for the next candle to show which side wins."
    else:
        txt += f" It agrees with the {trend}, which makes it a little more meaningful."
    if x["days_ago"] == 0:
        txt += " It formed today, so traders wait for **confirmation** (the next candle moving the same way) before trusting it."
    return txt


def _technical_view(s):
    p, t = s["price"], s["tech"]
    c = p["close"]

    def rel(v):
        return "n/a" if v is None else f"{'above' if c >= v else 'below'} its {{}} ({rs(v, 1)})"
    parts = [f"The trend is **{t['trend'].lower()}**: price is {rel(t['sma20']).format('20 DMA')}, {rel(t['sma50']).format('50 DMA')} "
             f"and {rel(t['sma200']).format('200 DMA')} (**DMA** = the average closing price of the last 20/50/200 days)."]
    r = t["rsi"]
    if r is not None:
        lab = ("overbought - it has run up fast and may cool off" if r >= 70 else
               "oversold - it has fallen fast and may bounce" if r <= 30 else
               "positive momentum" if r >= 55 else "weak momentum" if r <= 45 else "neutral")
        parts.append(f"**RSI** (a 0-100 speed meter of price moves) is {r:.0f}: {lab}.")
    parts.append(f"**MACD** (a momentum indicator) is {'bullish' if t['macd_bullish'] else 'bearish'}"
                 f"{', with a fresh crossover today' if t['macd_cross_today'] else ''}.")
    vr = p["vol_ratio"]
    if vr:
        note = ("unusually high interest" if vr >= 1.5 else "thin trading, so the move is less convincing" if vr < 0.8 else "normal activity")
        parts.append(f"Volume was {vr:.2f}x its 20-day average - {note}.")
    parts.append(f"**Support** (a price floor where buyers appeared before) is near {rs(t['support'], 1)}; "
                 f"**resistance** (a ceiling where sellers appeared before) is near {rs(t['resistance'], 1)}.")
    return " ".join(parts)


def _fundamental_view(s):
    f = s["fund"]
    parts = []
    if f.get("pe") is not None:
        pe = f["pe"]
        lab = ("loss-making" if pe <= 0 else "cheap" if pe < 20 else "fairly valued" if pe <= 40 else "expensive")
        parts.append(f"**P/E** (price divided by yearly profit per share) is {pe:.1f}, which looks {lab}.")
    if f.get("roe") is not None:
        parts.append(f"**ROE** (profit earned on shareholders' money) is {f['roe']:.1f}%"
                     f" - {'good (above 15%)' if f['roe'] >= 15 else 'below the 15% mark'}.")
    if f.get("de") is not None:
        parts.append(f"**Debt-to-equity** is {f['de']:.2f}x - {'low debt' if f['de'] < 0.5 else 'high debt' if f['de'] > 1.5 else 'moderate debt'}.")
    g = []
    if f.get("rev_growth") is not None:
        g.append(f"revenue {f['rev_growth']:+.1f}%")
    if f.get("profit_growth") is not None:
        g.append(f"profit {f['profit_growth']:+.1f}%")
    if g:
        txt = "Year-on-year growth: " + ", ".join(g) + "."
        if f.get("rev_growth") is not None and abs(f["rev_growth"]) > 60:
            txt += " (Such a big jump usually comes from a merger or an accounting change, not normal growth.)"
        parts.append(txt)
    return " ".join(parts) or "Fundamental data was not available today."


def _summary(s):
    p, t, f = s["price"], s["tech"], s["fund"]
    move = f"{'rose' if p['pct'] >= 0 else 'fell'} {abs(p['pct']):.2f}%"
    rel = "beat" if p["vs_nifty"] >= 0 else "lagged"
    val = ""
    if f.get("pe") is not None and f["pe"] > 0:
        val = f" Valuation looks {'cheap' if f['pe'] < 20 else 'fair' if f['pe'] <= 40 else 'expensive'} (P/E {f['pe']:.1f})."
    return f"{s['name']} {move} today and {rel} the Nifty by {abs(p['vs_nifty']):.2f} points. The chart trend is {t['trend'].lower()}.{val}"


def _watch_next(s):
    t, f = s["tech"], s["fund"]
    txt = (f"A close above {rs(t['resistance'], 1)} would be a **breakout**; a close below {rs(t['support'], 1)} would be a **breakdown**.")
    if f.get("next_results"):
        txt += f" Quarterly results are due on {f['next_results']} - expect bigger moves around that day."
    return txt


def _tracker_insight(d):
    rows = [t for t in d["tracker"] if t["bias"] != "neutral" and t["count"] >= 30 and t.get("win3") is not None]
    if not rows:
        return ""
    best, worst = max(rows, key=lambda t: t["win3"]), min(rows, key=lambda t: t["win3"])
    avg = sum(t["win3"] for t in rows) / len(rows)
    return (f"Across {len(rows)} patterns seen at least 30 times, the average 3-day win rate is {avg:.0f}% - close to a coin toss. "
            f"The best was {best['pattern']} ({best['win3']}%) and the weakest was {worst['pattern']} ({worst['win3']}%). "
            "So never trade a pattern alone - combine it with the trend, support/resistance and volume.")


def build_auto(d):
    stocks = {}
    for s in d["stocks"]:
        stocks[s["symbol"]] = {
            "chart_reading": _chart_reading(s),
            "why_it_moved": "No specific news was checked for this stock today - compare its move with its sector and the overall market on page 1.",
            "pattern_lesson": _pattern_lesson(s),
            "technical_view": _technical_view(s),
            "fundamental_view": _fundamental_view(s),
            "summary": _summary(s),
            "watch_next": _watch_next(s),
        }
    return {"stocks": stocks, "tracker_insight": _tracker_insight(d)}


def merge(auto, n):
    """Claude's narrative.json overrides the auto text field by field."""
    out = dict(auto)
    for k, v in (n or {}).items():
        if k == "stocks":
            st = {sym: dict(fields) for sym, fields in auto.get("stocks", {}).items()}
            for sym, fields in (v or {}).items():
                st.setdefault(sym, {}).update({a: b for a, b in fields.items() if b})
            out["stocks"] = st
        elif v:
            out[k] = v
    return out
