# Daily routine (for Claude) - be fast and token-frugal

Produce today's NSE Daily Market Report PDF and email it. Python does all data work and writes most of the
report text automatically. **Your job is only the parts that need judgement.**
Token rules: read only `out/brief.md`; no exploring; no viewing the PDF or images; don't re-read files you wrote;
no long chat output; do the steps in as few tool calls as possible.

## 1. Collect (one command)
```bash
pip install -q -r requirements.txt && python -W ignore -m src.collect
```
- Exit code **3** = market holiday/weekend → reply "No session today." and **stop** (no email).
- Other error: retry once; if it still fails run `python -m src.send_email --error "<short reason>"` and stop.

## 2. Read `out/brief.md` (small). Stocks are sorted by size of move.

## 3. News - at most 3 web searches, then stop
1. `Sensex Nifty closing today <date> FII DII` - why the market moved + FII/DII numbers.
2-3. One search each for the **2 biggest movers** in the brief (stock name + "share price today").
If the first search shows nothing dated today, skip searches 2-3. Only state news you actually found.

## 4. Write `out/narrative.json` (one file write)
Simple English for a complete beginner; explain each market term in brackets the first time it appears
(`**bold**` the term). Use real numbers from the brief. Educational tone: say what traders *watch*; never say
buy/sell/target and never predict prices. Include ONLY these keys (the rest is filled in automatically):

```json
{
  "headline": "one line: the main story of the day",
  "market_story": ["exactly 5 short lines: Nifty move, what led/lagged, breadth, VIX, one global/crude/rupee point"],
  "global_and_flows": "2-3 sentences: global cues, crude, rupee, FII/DII figures if found",
  "lesson": {
    "title": "lesson title from the brief",
    "explanation": ["3-4 short paragraphs teaching the topic from zero"],
    "example_from_today": "point to a real stock/chart/number in today's report that shows it",
    "key_takeaway": "one sentence"
  },
  "stocks": {
    "<SYMBOL>": {"why_it_moved": "ONE sentence: news if found, else the sector/market link"}
  },
  "extra_terms": {"new term used": "simple meaning"},
  "sources": ["urls of news used"]
}
```
`stocks` must include **every** symbol in the brief, `why_it_moved` only (one sentence each, ≤25 words).
Optionally add `"summary"` for a stock only if something unusual happened (e.g. volume ≥2x, new 52-week low).

## 5. Build + send (one command)
```bash
python -W ignore -m src.pdf_report && python -m src.send_email
```
If it fails, read the error once, fix the JSON, retry once. Do not commit or push.
Final reply: **one line** - date, Nifty move, stocks count, emailed yes/no.
