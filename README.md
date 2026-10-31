# NSE Daily Market Report

An automatic, beginner-friendly **daily PDF report on Indian stocks**, emailed after market close.
Built to *learn* the stock market: every term is explained, every chart is annotated, and a 60-day
course teaches one concept per trading day using that day's real market.

> **For education only. Not investment advice.** The author is not a SEBI-registered adviser or research analyst.
> Data comes from free Yahoo Finance endpoints and may be delayed, incomplete or wrong.

## What's in the PDF (~40 pages)

| Section | Contents |
|---|---|
| Market Dashboard | Nifty 50, Sensex, Bank Nifty, India VIX, Nifty intraday chart, sector heat bars, top gainers/losers, breadth, global markets, crude, USD/INR |
| Today in 5 lines | Plain-English story of the day |
| Lesson of the Day | 60-lesson beginner course (shares → candles → trends → indicators → fundamentals → risk), taught with today's charts |
| Stock pages (3 per stock) | Price card · 5-min intraday chart with VWAP & opening range · "how the day played out" · why it moved (news) · 6-month candle chart with 20/50/200 DMA, support/resistance and pattern markers · candlestick patterns with **their track record on that stock** · technical table · fundamental table · summary & what to watch |
| Pattern Tracker | How often each candlestick pattern actually worked on these stocks over 2 years |
| Market Dictionary | All terms in simple words |

Default stocks: HDFC Bank, ICICI Bank, Infosys, TCS, Reliance, ITC, Maruti, Sun Pharma, Tata Steel, Bharti Airtel,
Jio Financial Services - edit [`config.yaml`](config.yaml) to change them.

## How it works

```
Mon-Fri ~5:00 PM IST  - Claude Code Routine (runs in Anthropic's cloud on a Claude subscription)
  1. python -m src.collect      data + indicators + 22 candlestick patterns + charts   (no AI)
  2. Claude reads out/brief.md, does a few news searches, writes out/narrative.json
  3. python -m src.pdf_report   builds the PDF                                         (no AI)
  4. python -m src.send_email   emails it (BCC) to everyone in REPORT_RECIPIENTS        (no AI)
```
The full instructions Claude follows are in [`ROUTINE_PROMPT.md`](ROUTINE_PROMPT.md).
Holidays/weekends are detected automatically (no new market data → the run stops without emailing).

## Setup (one time)

### 1. Gmail App Password (for sending)
1. Turn on **2-Step Verification**: <https://myaccount.google.com/signinoptions/twosv>
2. Create an **App Password**: <https://myaccount.google.com/apppasswords> → name it `NSE report` → copy the 16-character code.

### 2. Create the Claude Routine
1. Open <https://claude.ai/code> and connect your GitHub account (install the Claude GitHub app on this repo).
2. Create a **cloud environment** with:
   - **Network access:** *Full* (it needs Yahoo Finance, Gmail SMTP and pip).
   - **Environment variables** (private - never put these in the repo):
     ```
     GMAIL_USER=yoursender@gmail.com
     GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
     REPORT_RECIPIENTS=you@gmail.com, second@gmail.com, third@outlook.com
     ```
3. Create a **Routine** → select this repo + environment → model **Sonnet** → schedule **weekdays 17:00 IST** (11:30 UTC) →
   prompt: `Follow ROUTINE_PROMPT.md exactly.`
4. Click **Run now** once and check your inbox and *Settings → Usage*.

**Claude cloud environments block SMTP**, so use the free Google Apps Script sender (sends from your own Gmail over HTTPS):
1. Open <https://script.google.com> signed in with the sender Gmail → **New project** → paste [`tools/gmail_sender.gs`](tools/gmail_sender.gs).
2. **Project Settings → Script properties → Add**: `MAIL_TOKEN` = any long random text.
3. Select function `authorize` → **Run** → allow Gmail access.
4. **Deploy → New deployment → Web app** (Execute as: *Me*, Who has access: *Anyone*) → copy the **Web app URL**.
5. In the Claude environment add `APPS_SCRIPT_URL=<that URL>` and `MAIL_TOKEN=<same text>`.

Alternatively, create a free [Brevo](https://www.brevo.com) account, verify your
sender email, and add `BREVO_API_KEY=...` (and optionally `BREVO_SENDER=...`) to the environment. The script falls back to it automatically.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.collect --allow-old   # --allow-old = use last session even if today is a holiday
# (optional) write out/narrative.json yourself or with Claude - without it you get a data-only PDF
.venv/bin/python -m src.pdf_report
REPORT_RECIPIENTS=you@gmail.com GMAIL_USER=... GMAIL_APP_PASSWORD=... .venv/bin/python -m src.send_email
```

## Project layout

```
config.yaml            stocks, indices, branding, course start date
ROUTINE_PROMPT.md      instructions for the daily Claude run
content/curriculum.yaml  60-day beginner course
content/glossary.yaml    market dictionary
src/collect.py         data download, analysis, charts, brief.md
src/indicators.py      DMA, RSI, MACD, ATR, VWAP, support/resistance
src/patterns.py        22 candlestick patterns + pattern tracker
src/charts.py          chart images
src/pdf_report.py      PDF layout
src/send_email.py      Gmail SMTP / Brevo sender
```

## License
MIT - see [LICENSE](LICENSE).
