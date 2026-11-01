"""Step 3: build the PDF from out/data.json (+ out/narrative.json written by Claude)."""
import json
import os
import re
import sys
from xml.sax.saxutils import escape

import matplotlib
import yaml
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

# DejaVu ships with matplotlib and supports the rupee sign and bullet symbols
_fdir = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(_fdir, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(_fdir, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", os.path.join(_fdir, "DejaVuSans-Oblique.ttf")))
from reportlab.lib.fonts import addMapping
addMapping("DV", 0, 0, "DV"); addMapping("DV", 1, 0, "DVB"); addMapping("DV", 0, 1, "DVI"); addMapping("DV", 1, 1, "DVB")

NAVY = colors.HexColor("#14213d")
BLUE = colors.HexColor("#2f6fdb")
LIGHT = colors.HexColor("#f2f5fa")
GREEN = colors.HexColor("#1a9e5c")
RED = colors.HexColor("#d64545")
AMBER = colors.HexColor("#c98a00")
GREY = colors.HexColor("#666666")
SIG = {"good": (GREEN, "● Good"), "bad": (RED, "● Weak"), "neutral": (AMBER, "● Neutral")}
W = A4[0] - 3 * cm

S = {
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=20, leading=24, textColor=colors.white),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=10, leading=13, textColor=colors.white),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=14, leading=18, textColor=NAVY, spaceBefore=8, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="DVB", fontSize=11, leading=14, textColor=BLUE, spaceBefore=6, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="DV", fontSize=9.5, leading=13.5, spaceAfter=4),
    "small": ParagraphStyle("small", fontName="DV", fontSize=8, leading=10.5, textColor=GREY),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=8, leading=10),
    "cellb": ParagraphStyle("cellb", fontName="DVB", fontSize=8, leading=10),
    "cellh": ParagraphStyle("cellh", fontName="DVB", fontSize=8, leading=10, textColor=colors.white),
    "box": ParagraphStyle("box", fontName="DV", fontSize=9.5, leading=13.5),
    "center": ParagraphStyle("center", fontName="DV", fontSize=9, leading=12, alignment=TA_CENTER, textColor=GREY),
}


def md(text):
    """Escape text and turn **bold** into <b>bold</b>."""
    if text is None:
        return ""
    t = escape(str(text))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def P(text, style="body"):
    return Paragraph(md(text), S[style])


def pct_color(v):
    return GREEN if (v or 0) >= 0 else RED


def img(path, width=W):
    if not path or not os.path.exists(path):
        return P("(chart not available)", "small")
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


def table(rows, widths, header=True, zebra=True, extra=None):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [("FONTNAME", (0, 0), (-1, -1), "DV"), ("FONTSIZE", (0, 0), (-1, -1), 8),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d6e0")),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "DVB")]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(st + (extra or [])))
    return t


def box(flowables, bg=LIGHT, border=BLUE):
    t = Table([[flowables]], colWidths=[W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, border),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def banner(title, subtitle, right=""):
    t = Table([[[Paragraph(md(title), S["h1"]), Paragraph(md(subtitle), S["sub"])], Paragraph(right, S["sub"])]],
              colWidths=[W * 0.72, W * 0.28])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 10),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    return t


def signal_rows(rows):
    out = [[Paragraph(h, S["cellh"]) for h in ("Field", "Value", "Signal", "What it means")]]
    extra = []
    for i, r in enumerate(rows, start=1):
        col, lab = SIG[r["signal"]]
        out.append([Paragraph(md(r["field"]), S["cellb"]), Paragraph(md(r["value"]), S["cell"]),
                    Paragraph(f'<font color="{col.hexval()}">{lab}</font>', S["cell"]), Paragraph(md(r["meaning"]), S["cell"])])
    return table(out, [3.2 * cm, 4.4 * cm, 1.8 * cm, W - 9.4 * cm], extra=extra)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7)
    canvas.setFillColor(GREY)
    canvas.drawString(1.5 * cm, 0.9 * cm, "For education only - not investment advice. Data: Yahoo Finance (may be delayed/incomplete).")
    canvas.drawRightString(A4[0] - 1.5 * cm, 0.9 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ------------------------------------------------------------------ sections
def dashboard(d, n):
    m = d["market"]
    story = [banner(d["config"]["title"], d["config"]["subtitle"],
                    f"{md(d['session_date_human'])}<br/>Course day {d['course_day']}"), Spacer(1, 8)]
    if n.get("headline"):
        story.append(P(f"**{n['headline']}**", "h2"))
    if n.get("market_story"):
        story.append(P("Today in 5 lines", "h3"))
        story.append(box([P("• " + line, "box") for line in n["market_story"]]))
    story.append(P("Market Dashboard", "h2"))
    rows = [["Index", "Close", "Change", "% Change", "What it means"]]
    extra = []
    for i, x in enumerate(m["indices"], start=1):
        rows.append([Paragraph(f"<b>{md(x['name'])}</b>", S["cell"]), f"{x['close']:,.2f}", f"{x['chg']:+,.2f}",
                     f"{x['pct']:+.2f}%", Paragraph(md(x["meaning"]), S["cell"])])
        extra.append(("TEXTCOLOR", (2, i), (3, i), pct_color(x["pct"])))
    story.append(table(rows, [2.6 * cm, 2.4 * cm, 2.2 * cm, 2 * cm, W - 9.2 * cm], extra=extra))
    b = m["breadth"]
    story.append(Spacer(1, 4))
    story.append(P(f"**Market breadth** (Nifty 50 stocks): {b['advances']} went up, {b['declines']} went down. "
                   "Breadth tells you if a move is broad (most stocks join in) or narrow (only a few heavyweights moved the index).", "small"))
    story.append(Spacer(1, 4))
    story.append(img(m["charts"].get("nifty")))
    story.append(P("Line above the dotted line (yesterday's close) = Nifty was up at that time; below = down.", "small"))
    story.append(CondPageBreak(9 * cm))
    story.append(img(m["charts"].get("sectors")))
    story.append(P("Sector indices show which industries money flowed into (green) or out of (red) today.", "small"))
    # gainers / losers side by side
    def gl(items, title, col):
        r = [[title, "Close", "%"]]
        for x in items:
            r.append([x["symbol"], f"{x['close']:,.1f}", f"{x['pct']:+.2f}%"])
        return table(r, [4.2 * cm, 2.2 * cm, 1.8 * cm], extra=[("TEXTCOLOR", (2, 1), (2, -1), col)])
    two = Table([[gl(m["gainers"], "Top Gainers (Nifty 50)", GREEN), gl(m["losers"], "Top Losers (Nifty 50)", RED)]],
                colWidths=[W / 2, W / 2])
    story += [Spacer(1, 6), two, Spacer(1, 6)]
    rows = [["Global / Macro", "Last", "% Change", "Why it matters for India"]]
    extra = []
    for i, x in enumerate(m["global"], start=1):
        rows.append([x["name"], f"{x['close']:,.2f}", f"{x['pct']:+.2f}%", Paragraph(md(x["meaning"]), S["cell"])])
        extra.append(("TEXTCOLOR", (2, i), (2, i), pct_color(x["pct"])))
    story.append(table(rows, [3.4 * cm, 2.4 * cm, 2 * cm, W - 7.8 * cm], extra=extra))
    if n.get("global_and_flows"):
        story += [P("Global cues & money flows (FII / DII)", "h3"), P(n["global_and_flows"])]
    return story


def lesson(d, n, curriculum):
    day = d["course_day"]
    c = curriculum[min(day, len(curriculum)) - 1]
    L = n.get("lesson") or {}
    story = [PageBreak(), banner(f"Lesson of the Day #{day}", c["week"] if day <= len(curriculum) else "Review mode"), Spacer(1, 8),
             P(L.get("title") or c["title"], "h2")]
    if L:
        for para in L.get("explanation", []):
            story.append(P(para))
        if L.get("example_from_today"):
            story += [P("Real example from today's market", "h3"), box([P(L["example_from_today"], "box")], bg=colors.HexColor("#eef7f1"), border=GREEN)]
        if L.get("key_takeaway"):
            story += [Spacer(1, 6), box([P("**Key takeaway:** " + L["key_takeaway"], "box")], bg=colors.HexColor("#fff7e6"), border=AMBER)]
    else:
        story.append(P("Terms for today: " + ", ".join(c["terms"]) + ". (Lesson text not generated today - see glossary at the end.)"))
    return story


def stock_pages(s, n):
    sn = (n.get("stocks") or {}).get(s["symbol"], {})
    p, it = s["price"], s["intraday"]
    col = "#1a9e5c" if p["pct"] >= 0 else "#d64545"
    story = [PageBreak(), banner(f"{s['name']}  ({s['symbol']})", f"{s['sector']}" + (f" · {s['industry']}" if s.get("industry") else ""),
                                 f'<font size="16"><b>Rs {p["close"]:,.2f}</b></font><br/><font color="{"#7CFFB2" if p["pct"] >= 0 else "#FF9C9C"}">{p["chg"]:+,.2f} ({p["pct"]:+.2f}%)</font>'),
             Spacer(1, 6)]
    card = [["Open", "High", "Low", "Prev Close", "Gap at open", "Volume vs avg", "Beat Nifty by" if p["vs_nifty"] >= 0 else "Lagged Nifty by"],
            [f"{p['open']:,.2f}", f"{p['high']:,.2f}", f"{p['low']:,.2f}", f"{p['prev_close']:,.2f}", f"{p['gap_pct']:+.2f}%",
             f"{p['vol_ratio']}x" if p["vol_ratio"] else "n/a", f"{p['vs_nifty']:+.2f}%"]]
    story.append(table(card, [W / 7] * 7, zebra=False,
                       extra=[("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TEXTCOLOR", (6, 1), (6, 1), pct_color(p["vs_nifty"])),
                              ("TEXTCOLOR", (4, 1), (4, 1), pct_color(p["gap_pct"]))]))
    story.append(P(f"Opening range (9:15-9:30): {it['or_low']:,} - {it['or_high']:,} · Day high at {it['high_time']}, day low at {it['low_time']} · "
                   f"Closed {it['close_vs_vwap']} VWAP ({it['vwap_close']:,}) · Biggest 5-min move: {it['biggest_5m_move']} · Day range {it['range_pct']}%", "small"))
    story += [Spacer(1, 4), img(s["charts"]["intraday"])]
    if sn.get("chart_reading"):
        story += [P("How the day played out (9:15 → 3:30)", "h3"), P(sn["chart_reading"])]
    if sn.get("why_it_moved"):
        story += [P("Why did it move?", "h3"), box([P(sn["why_it_moved"], "box")])]

    if sn.get("summary") or sn.get("watch_next"):
        parts = []
        if sn.get("summary"):
            parts.append(P("**Summary:** " + sn["summary"], "box"))
        if sn.get("watch_next"):
            parts.append(P("**What to watch next:** " + sn["watch_next"], "box"))
        story += [Spacer(1, 6), KeepTogether(box(parts, bg=colors.HexColor("#eef7f1"), border=GREEN))]

    story += [PageBreak(), P(f"{s['name']} - bigger picture: 6-month chart", "h3"), img(s["charts"]["daily"]),
              P("▲ green = bullish pattern, ▼ red = bearish pattern, ◆ grey = neutral (last 5 days). Dashed lines = support (green) and resistance (red).", "small")]
    story.append(P("Candlestick patterns (last 5 trading days)", "h3"))
    if s["patterns"]:
        rows = [[Paragraph(h, S["cellh"]) for h in ("Date", "Pattern", "Type", "What it means", "Track record on this stock")]]
        extra = []
        for i, x in enumerate(s["patterns"], start=1):
            c = GREEN if x["bias"] == "bullish" else RED if x["bias"] == "bearish" else AMBER
            rows.append([x["date"], Paragraph(f"<b>{md(x['pattern'])}</b>", S["cell"]),
                         Paragraph(f'<font color="{c.hexval()}">{x["bias"].title()}</font>', S["cell"]),
                         Paragraph(md(x["meaning"]), S["cell"]), Paragraph(md(x["history"]), S["cell"])])
        story.append(table(rows, [1.4 * cm, 2.8 * cm, 1.6 * cm, W - 10.3 * cm, 4.5 * cm], extra=extra))
    else:
        story.append(P("No clear candlestick pattern in the last 5 days.", "small"))
    if sn.get("pattern_lesson"):
        story.append(Spacer(1, 4))
        story.append(box([P("**Pattern check:** " + sn["pattern_lesson"], "box")], bg=colors.HexColor("#f5f0ff"), border=colors.HexColor("#7a3db8")))

    story += [CondPageBreak(8 * cm), P("Technical analysis (price & chart based)", "h3"), signal_rows(s["tech_rows"])]
    if sn.get("technical_view"):
        story += [Spacer(1, 3), P("**In simple words:** " + sn["technical_view"])]
    story += [CondPageBreak(7 * cm), P("Fundamental analysis (business health)", "h3"), signal_rows(s["fund_rows"])]
    if sn.get("fundamental_view"):
        story += [Spacer(1, 3), P("**In simple words:** " + sn["fundamental_view"])]
    return story


def tracker(d, n):
    story = [PageBreak(), banner("Pattern Tracker", "What really happened after each pattern - last 2 years, all report stocks"), Spacer(1, 8),
             P("Every time a pattern appeared on one of our stocks in the last 2 years, we checked the price 1, 3 and 5 trading days later. "
               "**Win %** = how often price moved the way the pattern 'predicts' (up for bullish, down for bearish). "
               "Around 50% means the pattern alone is no better than a coin toss - that is why traders combine patterns with trend, "
               "support/resistance and volume.")]
    rows = [[Paragraph(h, S["cellh"]) for h in ("Pattern", "Type", "Times seen", "Win % 1 day", "Win % 3 days", "Win % 5 days", "Avg move 5 days")]]
    extra = []
    for i, t in enumerate(d["tracker"], start=1):
        c = GREEN if t["bias"] == "bullish" else RED if t["bias"] == "bearish" else AMBER
        def w(v):
            return "-" if v is None else f"{v}%"
        rows.append([t["pattern"], Paragraph(f'<font color="{c.hexval()}">{t["bias"].title()}</font>', S["cell"]), str(t["count"]),
                     w(t["win1"]), w(t["win3"]), w(t["win5"]), f"{t['avg5']:+.2f}%"])
        for j, k in ((3, "win1"), (4, "win3"), (5, "win5")):
            v = t[k]
            if v is not None and v >= 60:
                extra.append(("TEXTCOLOR", (j, i), (j, i), GREEN))
            elif v is not None and v <= 40:
                extra.append(("TEXTCOLOR", (j, i), (j, i), RED))
    story.append(table(rows, [4 * cm, 1.8 * cm, 2 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm, W - 14.4 * cm], extra=extra))
    if n.get("tracker_insight"):
        story += [Spacer(1, 6), box([P("**What this teaches us:** " + n["tracker_insight"], "box")])]
    return story


def glossary(n):
    with open(os.path.join(ROOT, "content", "glossary.yaml")) as f:
        g = yaml.safe_load(f)
    for k, v in (n.get("extra_terms") or {}).items():
        g.setdefault(k, v)
    story = [PageBreak(), banner("Market Dictionary", "Every term used in this report, in simple words"), Spacer(1, 8)]
    rows = [[Paragraph(f"<b>{md(k)}</b>", S["cell"]), Paragraph(md(v), S["cell"])] for k, v in g.items()]
    story.append(table(rows, [4 * cm, W - 4 * cm], header=False))
    return story


def disclaimer(d, n):
    story = [Spacer(1, 12), P("Important", "h3"), P(
        "This report is generated automatically for **personal learning only**. It is **not investment advice** and not a "
        "recommendation to buy or sell any security. The author is not a SEBI-registered investment adviser or research analyst. "
        "Candlestick patterns and indicators are probabilities, not guarantees. Data comes from free sources (Yahoo Finance) and may "
        "be delayed, incomplete or wrong. Always do your own research and practise with paper trading before risking real money.", "small")]
    if n.get("sources"):
        story += [P("News sources used today", "h3")] + [P(u, "small") for u in n["sources"][:20]]
    if d.get("failed"):
        story.append(P("Could not load today: " + ", ".join(d["failed"]), "small"))
    story.append(P(f"Generated {d['generated_at']}.", "small"))
    return story


def build(out_path=None):
    with open(os.path.join(OUT, "data.json")) as f:
        d = json.load(f)
    npath = os.path.join(OUT, "narrative.json")
    n = {}
    if os.path.exists(npath):
        with open(npath) as f:
            n = json.load(f)
    else:
        print("WARN: out/narrative.json missing - using automatic text only", file=sys.stderr)
    from .auto_text import build_auto, merge
    n = merge(build_auto(d), n)
    with open(os.path.join(ROOT, "content", "curriculum.yaml")) as f:
        curriculum = yaml.safe_load(f)
    out_path = out_path or os.path.join(OUT, f"NSE_Daily_Report_{d['session_date']}.pdf")
    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm,
                            bottomMargin=1.5 * cm, title=f"{d['config']['title']} - {d['session_date']}", author="NSE Daily Market Report")
    story = dashboard(d, n) + lesson(d, n, curriculum)
    for s in d["stocks"]:
        story += stock_pages(s, n)
    story += tracker(d, n) + glossary(n) + disclaimer(d, n)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"OK: PDF written to {out_path} ({os.path.getsize(out_path) / 1e6:.1f} MB)")
    return out_path


if __name__ == "__main__":
    build()
