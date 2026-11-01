"""Chart images (PNG) for the PDF, built with mplfinance / matplotlib."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

UP, DOWN = "#1a9e5c", "#d64545"
STYLE = mpf.make_mpf_style(
    base_mpf_style="yahoo",
    marketcolors=mpf.make_marketcolors(up=UP, down=DOWN, edge="inherit", wick="inherit", volume="inherit"),
    gridstyle=":", gridcolor="#dddddd", facecolor="white", rc={"font.size": 9},
)


def daily_chart(df: pd.DataFrame, title: str, support: float, resistance: float, patterns: list[dict], path: str):
    d = df.tail(130)
    adds = []
    for col, color in (("SMA20", "#2f6fdb"), ("SMA50", "#f08c00"), ("SMA200", "#7a3db8")):
        if d[col].notna().any():
            adds.append(mpf.make_addplot(d[col], color=color, width=1.1))
    # pattern markers on the last 5 candles
    bull = pd.Series(np.nan, index=d.index)
    bear = pd.Series(np.nan, index=d.index)
    neut = pd.Series(np.nan, index=d.index)
    for p in patterns:
        idx = d.index[len(d) - 1 - p["days_ago"]]
        if p["bias"] == "bullish":
            bull[idx] = d.loc[idx, "Low"] * 0.985
        elif p["bias"] == "bearish":
            bear[idx] = d.loc[idx, "High"] * 1.015
        else:
            neut[idx] = d.loc[idx, "High"] * 1.015
    if bull.notna().any():
        adds.append(mpf.make_addplot(bull, type="scatter", marker="^", markersize=90, color=UP))
    if bear.notna().any():
        adds.append(mpf.make_addplot(bear, type="scatter", marker="v", markersize=90, color=DOWN))
    if neut.notna().any():
        adds.append(mpf.make_addplot(neut, type="scatter", marker="D", markersize=50, color="#888888"))
    fig, axes = mpf.plot(
        d, type="candle", style=STYLE, volume=True, addplot=adds, returnfig=True,
        figsize=(10, 4.3), panel_ratios=(4, 1),
        hlines=dict(hlines=[support, resistance], colors=["#1a9e5c", "#d64545"], linestyle="--", linewidths=1),
        ylabel="Price (Rs)", ylabel_lower="Volume",
    )
    ax = axes[0]
    ax.set_title(f"{title} - last 6 months (daily candles)", fontsize=11, loc="left")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color="#2f6fdb", label="20 DMA"), Line2D([], [], color="#f08c00", label="50 DMA"),
               Line2D([], [], color="#7a3db8", label="200 DMA"),
               Line2D([], [], color=UP, ls="--", label=f"Support {support:,.0f}"),
               Line2D([], [], color=DOWN, ls="--", label=f"Resistance {resistance:,.0f}")]
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, ncol=5, frameon=False)
    fig.savefig(path, dpi=110, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def intraday_chart(intra: pd.DataFrame, title: str, prev_close: float, or_high: float, or_low: float, path: str):
    adds = [mpf.make_addplot(intra["VWAP"], color="#f08c00", width=1.2)]
    fig, axes = mpf.plot(
        intra, type="candle", style=STYLE, volume=True, addplot=adds, returnfig=True,
        figsize=(10, 4.2), panel_ratios=(4, 1), datetime_format="%H:%M",
        hlines=dict(hlines=[prev_close, or_high, or_low], colors=["#555555", "#2f6fdb", "#2f6fdb"],
                    linestyle=[":", "--", "--"], linewidths=1),
        ylabel="Price (Rs)", ylabel_lower="Volume",
    )
    ax = axes[0]
    ax.set_title(f"{title} - today 9:15 to 3:30 (5-minute candles)", fontsize=11, loc="left")
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color="#f08c00", label="VWAP"),
               Line2D([], [], color="#555555", ls=":", label=f"Yesterday close {prev_close:,.1f}"),
               Line2D([], [], color="#2f6fdb", ls="--", label="Opening range (first 15 min)")]
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, ncol=3, frameon=False)
    fig.savefig(path, dpi=110, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def bar_chart(labels: list[str], values: list[float], title: str, path: str, height=3.0):
    fig, ax = plt.subplots(figsize=(10, height))
    order = np.argsort(values)
    vals = [values[i] for i in order]
    labs = [labels[i] for i in order]
    ax.barh(labs, vals, color=[UP if v >= 0 else DOWN for v in vals])
    for y, v in enumerate(vals):
        ax.text(v, y, f" {v:+.2f}%", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_title(title, fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    lim = max(abs(min(vals)), abs(max(vals))) * 1.35 or 1
    ax.set_xlim(-lim, lim)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def index_intraday(intra: pd.DataFrame, title: str, prev_close: float, path: str):
    fig, ax = plt.subplots(figsize=(10, 2.6))
    x = np.arange(len(intra))
    ax.plot(x, intra["Close"], color="#2f6fdb", lw=1.4)
    ax.axhline(prev_close, color="#777", ls=":", lw=1)
    ax.fill_between(x, intra["Close"], prev_close, where=intra["Close"] >= prev_close, color=UP, alpha=0.15)
    ax.fill_between(x, intra["Close"], prev_close, where=intra["Close"] < prev_close, color=DOWN, alpha=0.15)
    ticks = [i for i, t in enumerate(intra.index) if t.minute == 0 or (t.hour == 9 and t.minute == 15)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([intra.index[i].strftime("%H:%M") for i in ticks], fontsize=8)
    ax.set_title(title, fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
