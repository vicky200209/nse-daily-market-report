"""Step 1: download market data, compute indicators/patterns, draw charts.

Writes:
  out/data.json   - everything the PDF needs
  out/brief.md    - compact summary for Claude to read (keeps token use low)
  out/charts/*.png
"""
import json
import math
import os
import sys
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

import pandas as pd
import yaml
import yfinance as yf

from . import charts
from . import indicators as ind
from . import patterns as pat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
CHARTS = os.path.join(OUT, "charts")
IST = ZoneInfo("Asia/Kolkata")


def load_config():
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)


def r(x, n=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, n)


def history(symbol, period="2y", interval="1d"):
    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    if df.empty:
        return df
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    if interval == "1d":
        df.index = pd.to_datetime(df.index.date)
    else:
        df.index = df.index.tz_convert(IST)
    return df


def last_session(intra):
    day = intra.index[-1].date()
    return intra[intra.index.date == day]


def quote(symbol):
    d = history(symbol, period="10d")
    if len(d) < 2:
        return None
    c, p = float(d["Close"].iloc[-1]), float(d["Close"].iloc[-2])
    return {"close": r(c), "prev": r(p), "chg": r(c - p), "pct": r((c / p - 1) * 100), "date": d.index[-1].strftime("%Y-%m-%d")}


# ---------- signal helpers: return (label, colour) where colour in good/neutral/bad ----------
def sig_rsi(v):
    if v is None: return ("n/a", "neutral")
    if v >= 70: return ("Overbought - may cool off", "bad")
    if v <= 30: return ("Oversold - may bounce", "neutral")
    if v >= 55: return ("Positive momentum", "good")
    if v <= 45: return ("Weak momentum", "bad")
    return ("Neutral", "neutral")


def sig_band(v, good_above, bad_below, fmt="{:.1f}%"):
    if v is None: return ("n/a", "neutral")
    if v >= good_above: return (fmt.format(v), "good")
    if v < bad_below: return (fmt.format(v), "bad")
    return (fmt.format(v), "neutral")


def fundamentals(symbol, sector):
    info = {}
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        pass
    fin = any(k in sector.lower() for k in ("bank", "financ", "nbfc"))
    pe = r(info.get("trailingPE"))
    roe = r((info.get("returnOnEquity") or float("nan")) * 100, 1)
    de = r((info.get("debtToEquity") or float("nan")) / 100, 2)
    rev = r((info.get("revenueGrowth") or float("nan")) * 100, 1)
    eg = r((info.get("earningsGrowth") or float("nan")) * 100, 1)
    pm = r((info.get("profitMargins") or float("nan")) * 100, 1)
    ins = r((info.get("heldPercentInsiders") or float("nan")) * 100, 1)
    inst = r((info.get("heldPercentInstitutions") or float("nan")) * 100, 1)
    dy = r(info.get("dividendYield"), 2)
    mcap = info.get("marketCap")
    earn = None
    try:
        cal = yf.Ticker(symbol).calendar or {}
        ed = cal.get("Earnings Date")
        future = [pd.to_datetime(x) for x in (ed or []) if pd.to_datetime(x).date() >= datetime.now(IST).date()]
        if future:
            earn = future[0].strftime("%d %b %Y")
    except Exception:
        pass

    def pe_sig(v):
        if v is None: return ("n/a", "neutral")
        if v <= 0: return (f"{v:.1f} (loss-making)", "bad")
        if v < 20: return (f"{v:.1f} - looks cheap", "good")
        if v <= 40: return (f"{v:.1f} - fairly valued", "neutral")
        return (f"{v:.1f} - expensive", "bad")

    rows = [
        {"field": "Market Cap", "value": f"Rs {mcap/1e7:,.0f} Cr" if mcap else "n/a", "signal": "neutral",
         "meaning": "Total value of all shares. Above Rs 1 lakh Cr = large-cap (big, stable company)."},
        {"field": "P/E Ratio", **dict(zip(("value", "signal"), pe_sig(pe))),
         "meaning": "Price / yearly profit per share. How many years of profit you pay for. Compare with peers."},
        {"field": "P/B Ratio", "value": f"{r(info.get('priceToBook'))}" if info.get("priceToBook") else "n/a", "signal": "neutral",
         "meaning": "Price / book value (net assets) per share. Important for banks."},
        {"field": "EPS (TTM)", "value": f"Rs {r(info.get('trailingEps'))}" if info.get("trailingEps") else "n/a", "signal": "neutral",
         "meaning": "Earnings Per Share - profit of last 12 months divided by number of shares."},
        {"field": "ROE", **dict(zip(("value", "signal"), sig_band(roe, 15, 10))),
         "meaning": "Return on Equity - profit made on shareholders' money. Above 15% is good."},
        {"field": "Debt / Equity", "value": "Not useful for banks/NBFCs" if fin else (f"{de:.2f}x" if de is not None else "n/a"),
         "signal": "neutral" if fin or de is None else ("good" if de < 0.5 else "bad" if de > 1.5 else "neutral"),
         "meaning": "Loans compared with owners' money. Below 0.5 = low debt (safer)."},
        {"field": "Revenue Growth (YoY)", **dict(zip(("value", "signal"), sig_band(rev, 10, 0))),
         "meaning": "How much sales grew vs the same quarter last year."},
        {"field": "Profit Growth (YoY)", **dict(zip(("value", "signal"), sig_band(eg, 10, 0))),
         "meaning": "How much net profit grew vs the same quarter last year."},
        {"field": "Profit Margin", **dict(zip(("value", "signal"), sig_band(pm, 15, 5))),
         "meaning": "Out of every Rs 100 of sales, how much is profit."},
        {"field": "Promoter / Insider Holding", "value": f"{ins:.1f}%" if ins is not None else "n/a", "signal": "neutral",
         "meaning": "Shares held by founders/promoters. High and stable = confidence in own company."},
        {"field": "Institutional Holding", "value": f"{inst:.1f}%" if inst is not None else "n/a", "signal": "neutral",
         "meaning": "Shares held by FIIs, mutual funds, insurance companies ('big money')."},
        {"field": "Dividend Yield", "value": f"{dy:.2f}%" if dy is not None else "n/a", "signal": "neutral",
         "meaning": "Yearly dividend as % of share price - cash paid to shareholders."},
        {"field": "Next Results Date", "value": earn or "n/a", "signal": "neutral",
         "meaning": "Quarterly results day - price often moves sharply around it."},
    ]
    raw = {"pe": pe, "roe": roe, "de": None if fin else de, "rev_growth": rev, "profit_growth": eg,
           "margin": pm, "insider": inst and ins, "inst": inst, "div_yield": dy, "mcap_cr": r(mcap / 1e7, 0) if mcap else None,
           "next_results": earn, "industry": info.get("industry")}
    return rows, raw


def analyse_stock(s, nifty_pct, all_outcomes):
    sym, name = s["symbol"], s["name"]
    code = sym.replace(".NS", "")
    daily = history(sym, "2y")
    intra_all = history(sym, "5d", "5m")
    if daily.empty or intra_all.empty:
        return None
    daily = ind.add_all(daily)
    intra = last_session(intra_all).copy()
    intra["VWAP"] = ind.vwap(intra)

    last, prev = daily.iloc[-1], daily.iloc[-2]
    close, pclose = float(last["Close"]), float(prev["Close"])
    pct = (close / pclose - 1) * 100
    support, resistance = ind.support_resistance(daily)
    recent = pat.recent_patterns(daily, days=5)
    outcomes = pat.forward_outcomes(daily)
    all_outcomes.extend(outcomes)
    own = pat.tracker_table(outcomes)
    own_map = {o["pattern"]: o for o in own}
    for p in recent:
        o = own_map.get(p["pattern"])
        p["history"] = (f"Seen {o['count']}x on {code} in 2 yrs; price moved the expected way "
                        f"{o['win3']}% of the time after 3 days" if o and o["win3"] is not None else
                        (f"Seen {o['count']}x on {code} in 2 yrs" if o else "First time in 2 yrs on this stock"))

    # intraday facts
    orng = intra.iloc[:3]
    or_hi, or_lo = float(orng["High"].max()), float(orng["Low"].min())
    hi_t = intra["High"].idxmax().strftime("%H:%M")
    lo_t = intra["Low"].idxmin().strftime("%H:%M")
    moves = intra["Close"].pct_change() * 100
    big = moves.abs().idxmax() if moves.notna().any() else None
    gap = (float(last["Open"]) / pclose - 1) * 100
    vol_ratio = float(last["Volume"]) / float(last["VolAvg20"]) if last["VolAvg20"] else None
    hi52, lo52 = float(daily["High"].tail(250).max()), float(daily["Low"].tail(250).min())

    rsi_v = r(last["RSI14"], 1)
    macd_bull = last["MACD"] > last["MACDsig"]
    macd_cross = (daily["MACD"].iloc[-2] <= daily["MACDsig"].iloc[-2]) != (last["MACD"] <= last["MACDsig"])
    trend = ind.trend_label(close, last["SMA20"], last["SMA50"], last["SMA200"])

    def above(ma):
        v = last[ma]
        if pd.isna(v): return ("n/a", "neutral")
        d = (close / v - 1) * 100
        return (f"{'Above' if d >= 0 else 'Below'} by {abs(d):.1f}% (Rs {v:,.1f})", "good" if d >= 0 else "bad")

    tech_rows = [
        {"field": "Trend", "value": trend, "signal": "good" if "up" in trend.lower() else "bad" if "down" in trend.lower() else "neutral",
         "meaning": "Overall direction using moving averages. Traders prefer buying in uptrends."},
        {"field": "vs 20 DMA", **dict(zip(("value", "signal"), above("SMA20"))), "meaning": "20-day average price = short-term trend (~1 month)."},
        {"field": "vs 50 DMA", **dict(zip(("value", "signal"), above("SMA50"))), "meaning": "50-day average = medium-term trend (~2.5 months)."},
        {"field": "vs 200 DMA", **dict(zip(("value", "signal"), above("SMA200"))), "meaning": "200-day average = long-term trend. Above it = long-term healthy."},
        {"field": "RSI (14)", "value": f"{rsi_v} - {sig_rsi(rsi_v)[0]}", "signal": sig_rsi(rsi_v)[1],
         "meaning": "Speed of price moves, 0-100. Above 70 = overbought, below 30 = oversold."},
        {"field": "MACD", "value": ("Bullish" if macd_bull else "Bearish") + (" - fresh crossover today!" if macd_cross else ""),
         "signal": "good" if macd_bull else "bad", "meaning": "Momentum indicator. MACD line above signal line = bullish."},
        {"field": "Volume vs 20-day avg", "value": f"{vol_ratio:.2f}x" if vol_ratio else "n/a",
         "signal": "good" if vol_ratio and vol_ratio >= 1.5 and pct > 0 else "bad" if vol_ratio and vol_ratio >= 1.5 and pct < 0 else "neutral",
         "meaning": "Above 1.5x = unusual interest. A big move on high volume is more trustworthy."},
        {"field": "Support / Resistance", "value": f"Rs {support:,.1f} / Rs {resistance:,.1f}", "signal": "neutral",
         "meaning": "Support = 'floor' where buyers came in before. Resistance = 'ceiling' where sellers came in."},
        {"field": "52-week High / Low", "value": f"Rs {hi52:,.1f} / Rs {lo52:,.1f}",
         "signal": "good" if close >= hi52 * 0.95 else "bad" if close <= lo52 * 1.05 else "neutral",
         "meaning": f"Price is {(1 - close / hi52) * 100:.1f}% below its 1-year high and {(close / lo52 - 1) * 100:.1f}% above its 1-year low."},
        {"field": "ATR (14)", "value": f"Rs {last['ATR14']:,.1f} ({last['ATR14'] / close * 100:.1f}% of price)", "signal": "neutral",
         "meaning": "Average True Range - how much the stock normally moves in a day. Used to set stop-losses."},
    ]
    fund_rows, fund_raw = fundamentals(sym, s["sector"])

    slug = code.lower().replace("&", "and")
    dpath, ipath = os.path.join(CHARTS, f"{slug}_daily.png"), os.path.join(CHARTS, f"{slug}_intraday.png")
    charts.daily_chart(daily, name, support, resistance, recent, dpath)
    charts.intraday_chart(intra, name, pclose, or_hi, or_lo, ipath)

    return {
        "symbol": code, "name": name, "sector": s["sector"], "industry": fund_raw.get("industry"),
        "price": {"open": r(last["Open"]), "high": r(last["High"]), "low": r(last["Low"]), "close": r(close),
                  "prev_close": r(pclose), "chg": r(close - pclose), "pct": r(pct), "vs_nifty": r(pct - nifty_pct),
                  "volume": int(last["Volume"]), "vol_ratio": r(vol_ratio), "gap_pct": r(gap)},
        "intraday": {"or_high": r(or_hi), "or_low": r(or_lo), "high_time": hi_t, "low_time": lo_t,
                     "vwap_close": r(intra["VWAP"].iloc[-1]), "close_vs_vwap": "above" if close >= intra["VWAP"].iloc[-1] else "below",
                     "biggest_5m_move": f"{moves[big]:+.2f}% at {big.strftime('%H:%M')}" if big is not None else None,
                     "range_pct": r((float(last["High"]) - float(last["Low"])) / pclose * 100)},
        "tech": {"trend": trend, "rsi": rsi_v, "macd_bullish": bool(macd_bull), "macd_cross_today": bool(macd_cross),
                 "sma20": r(last["SMA20"]), "sma50": r(last["SMA50"]), "sma200": r(last["SMA200"]),
                 "support": support, "resistance": resistance, "hi52": r(hi52), "lo52": r(lo52), "atr": r(last["ATR14"])},
        "tech_rows": tech_rows, "fund_rows": fund_rows, "fund": fund_raw,
        "patterns": recent,
        "charts": {"daily": dpath, "intraday": ipath},
    }


def market_overview(cfg, session_date):
    idx = []
    for i in cfg["indices"]:
        q = quote(i["symbol"])
        if q: idx.append({**i, **q})
    sectors = []
    for s in cfg["sectors"]:
        q = quote(s["symbol"])
        if q: sectors.append({"name": s["name"], "pct": q["pct"]})
    glob = []
    for g in cfg["global"]:
        q = quote(g["symbol"])
        if q: glob.append({**g, **q})
    # Nifty 50 breadth, gainers, losers
    tick = [f"{t}.NS" for t in cfg["nifty50"]]
    data = yf.download(tick, period="5d", interval="1d", progress=False, auto_adjust=False, group_by="ticker", threads=True)
    moves = []
    for t in tick:
        try:
            c = data[t]["Close"].dropna()
            if len(c) >= 2 and c.index[-1].strftime("%Y-%m-%d") == session_date:
                moves.append({"symbol": t.replace(".NS", ""), "close": r(c.iloc[-1]), "pct": r((c.iloc[-1] / c.iloc[-2] - 1) * 100)})
        except Exception:
            continue
    moves.sort(key=lambda x: x["pct"], reverse=True)
    adv = sum(1 for m in moves if m["pct"] > 0)
    dec = sum(1 for m in moves if m["pct"] < 0)
    # Nifty intraday chart
    ni = history("^NSEI", "5d", "5m")
    nifty_path = None
    if not ni.empty:
        ni = last_session(ni)
        prev = next((i["prev"] for i in idx if i["symbol"] == "^NSEI"), float(ni["Open"].iloc[0]))
        nifty_path = os.path.join(CHARTS, "nifty_intraday.png")
        charts.index_intraday(ni, "Nifty 50 - today's journey (5-minute)", prev, nifty_path)
    sector_path = None
    if sectors:
        sector_path = os.path.join(CHARTS, "sectors.png")
        charts.bar_chart([s["name"] for s in sectors], [s["pct"] for s in sectors], "Sector indices - today's % change", sector_path, 2.8)
    return {"indices": idx, "sectors": sectors, "global": glob, "breadth": {"advances": adv, "declines": dec, "total": len(moves)},
            "gainers": moves[:5], "losers": moves[-5:][::-1], "charts": {"nifty": nifty_path, "sectors": sector_path}}


def course_day(cfg, session_date):
    start = pd.Timestamp(cfg["report"]["course_start_date"])
    end = pd.Timestamp(session_date)
    if end < start:
        return 1
    return len(pd.bdate_range(start, end))


def write_brief(data, path):
    """Compact summary for Claude (~1.5k tokens). Stocks are sorted by size of move."""
    m = data["market"]
    with open(os.path.join(ROOT, "content", "curriculum.yaml")) as fh:
        cur = yaml.safe_load(fh)
    day = data["course_day"]
    if day <= len(cur):
        les = cur[day - 1]
        lesson_line = f"Lesson #{day} ({les['week']}): {les['title']} - terms: {', '.join(les['terms'])}"
    else:
        lesson_line = f"Lesson #{day}: REVIEW MODE - pick the concept most visible in today's market and re-teach it"
    L = [f"# Brief: {data['session_date_human']}", lesson_line, "",
         "Indices: " + "; ".join(f"{i['name']} {i['close']:,} ({i['pct']:+.2f}%)" for i in m["indices"]),
         f"Breadth (Nifty 50): {m['breadth']['advances']} up / {m['breadth']['declines']} down",
         "Sectors: " + ", ".join(f"{s['name']} {s['pct']:+.2f}%" for s in m["sectors"]),
         "Global: " + ", ".join(f"{g['name']} {g['pct']:+.2f}%" for g in m["global"]),
         "Top gainers: " + ", ".join(f"{g['symbol']} {g['pct']:+.2f}%" for g in m["gainers"]),
         "Top losers: " + ", ".join(f"{g['symbol']} {g['pct']:+.2f}%" for g in m["losers"]),
         "", "Our stocks, biggest move first (SYMBOL close %chg | volume vs avg | trend | RSI | patterns | next results):"]
    for s in sorted(data["stocks"], key=lambda x: -abs(x["price"]["pct"])):
        p, t, f = s["price"], s["tech"], s["fund"]
        pats = ", ".join(f"{x['pattern']}" for x in s["patterns"]) or "none"
        L.append(f"- {s['symbol']} ({s['sector']}) {p['close']:,} {p['pct']:+.2f}% | vol {p['vol_ratio']}x | {t['trend']} | RSI {t['rsi']} | {pats} | results {f['next_results'] or 'n/a'}")
    with open(path, "w") as fh:
        fh.write("\n".join(L))


def main(require_today: bool):
    os.makedirs(CHARTS, exist_ok=True)
    cfg = load_config()
    nifty = history("^NSEI", "10d")
    if nifty.empty:
        print("ERROR: could not download Nifty data", file=sys.stderr)
        sys.exit(2)
    session = nifty.index[-1]
    today = datetime.now(IST).date()
    if require_today and session.date() != today:
        print(f"NO_SESSION: last market session is {session.date()}, today is {today} (holiday/weekend). Nothing to do.")
        with open(os.path.join(OUT, "NO_SESSION"), "w") as fh:
            fh.write(str(session.date()))
        sys.exit(3)
    session_date = session.strftime("%Y-%m-%d")
    nifty_pct = (nifty["Close"].iloc[-1] / nifty["Close"].iloc[-2] - 1) * 100

    market = market_overview(cfg, session_date)
    stocks, all_outcomes, failed = [], [], []
    for s in cfg["stocks"]:
        try:
            res = analyse_stock(s, nifty_pct, all_outcomes)
            (stocks if res else failed).append(res or s["name"])
        except Exception as e:  # keep going - one bad stock must not kill the report
            print(f"WARN {s['symbol']}: {e}", file=sys.stderr)
            failed.append(s["name"])
    data = {
        "generated_at": datetime.now(IST).strftime("%d %b %Y %H:%M IST"),
        "session_date": session_date,
        "session_date_human": session.strftime("%A, %d %B %Y"),
        "course_day": course_day(cfg, session_date),
        "config": cfg["report"],
        "market": market,
        "stocks": stocks,
        "failed": failed,
        "tracker": pat.tracker_table(all_outcomes),
    }
    with open(os.path.join(OUT, "data.json"), "w") as fh:
        json.dump(data, fh, indent=1, default=str)
    write_brief(data, os.path.join(OUT, "brief.md"))
    print(f"OK: collected {len(stocks)} stocks for {session_date} (course day {data['course_day']}). Failed: {failed or 'none'}")


if __name__ == "__main__":
    main(require_today="--allow-old" not in sys.argv)
