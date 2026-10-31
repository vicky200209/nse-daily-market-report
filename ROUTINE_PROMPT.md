# Daily routine instructions (for Claude)

You are producing today's **NSE Daily Market Report** - a beginner-friendly, educational PDF - and emailing it.
Work efficiently: the Python scripts do all data work. Your only job is writing the explanations.
**Do not read any file except `out/brief.md`** (and error output if something fails). Do not explore the repo.

## Step 1 - Collect data
```bash
pip install -q -r requirements.txt
python -W ignore -m src.collect
```
- Exit code **3** (`NO_SESSION`) = market holiday/weekend. **Stop here.** Do not email. Reply "No session today."
- Any other error: retry once. If it still fails, run
  `python -m src.send_email --error "<one-line reason>"` and stop.

## Step 2 - Read the brief
Read `out/brief.md` (~3k tokens). It has indices, sectors, global markets, today's lesson topic,
and for every stock: prices, intraday story, technicals, candle patterns with their track record, fundamentals.

## Step 3 - News (4 to 8 web searches)
1. Search: "stock market today Sensex Nifty closing" (+ today's date) - why the market moved.
2. Search: "FII DII data today" (+ today's date).
3. Search the **3 biggest movers** among our stocks (largest absolute % change) by name + "share price today",
   plus any stock with volume ≥1.5x or results today. Don't search every stock.
   Searching by stock name + date works better than long queries.
Only state news you actually found. If no clear news, say the move followed the sector/market.

## Step 4 - Write `out/narrative.json`
Simple English for a complete beginner. The **first time a market term appears in a section, put it in
`**bold**` and explain it in brackets**, e.g. "**RSI** (a 0-100 speed meter of price moves) is 64".
Use real numbers from the brief. Educational tone: describe what traders *watch*, never say "buy"/"sell"/"target price"
and never predict prices. Keep each stock field 2-4 sentences.

```json
{
  "headline": "One line: the main story of the day",
  "market_story": ["5 short lines explaining today's market for a beginner"],
  "global_and_flows": "3-4 sentences: global cues, crude, rupee, FII/DII figures if found",
  "lesson": {
    "title": "Lesson title from the brief",
    "explanation": ["3-5 short paragraphs teaching the topic from zero"],
    "example_from_today": "Point to a real chart/stock in today's report that shows this concept",
    "key_takeaway": "One sentence"
  },
  "stocks": {
    "<SYMBOL e.g. INFY>": {
      "chart_reading": "Walk through the day 9:15 -> 3:30 using opening range, VWAP, day high/low times",
      "why_it_moved": "News / sector / market reason (from your searches), or 'no specific news - moved with X'",
      "pattern_lesson": "Explain the most important pattern on this stock and what its track record says",
      "technical_view": "Trend, DMAs, RSI, MACD, volume, support/resistance in plain words",
      "fundamental_view": "Is the business healthy? valuation, growth, ROE, debt in plain words",
      "summary": "2 sentences overall picture",
      "watch_next": "Levels/events a learner should watch (support, resistance, results date)"
    }
  },
  "tracker_insight": "2-3 sentences on what the Pattern Tracker table teaches",
  "extra_terms": {"Any new term you used": "simple meaning"},
  "sources": ["urls of news you used"]
}
```
Include **every** stock symbol from the brief. Write valid JSON (escape quotes).

## Step 5 - Build and send
```bash
python -W ignore -m src.pdf_report
python -m src.send_email
```
If the PDF step fails because of the narrative JSON, fix the JSON and retry. If email fails, report the exact error.
Do **not** commit or push anything. Finish with one line: date, Nifty move, number of stocks, emailed yes/no.
