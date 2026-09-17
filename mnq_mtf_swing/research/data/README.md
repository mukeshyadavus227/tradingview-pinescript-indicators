# MNQ historical bars (research data)

**Source:** TradingView, fetched through the tvremix MCP server (`get_ohlcv` tool).
**Symbol:** `CME_MINI:MNQ1!` (TradingView continuous front-month Micro E-mini Nasdaq-100 contract).
**Fetched:** 2026-09-16 (~00:16:40 UTC). Calls used `summary=false` with `count` = 5000 (15m), 5000 (1h), 3000 (4h) — the tool's maximum is 5000 bars per call, so each file is simply the most recent N bars available at fetch time.

The tool output does not state whether the continuous contract is roll-adjusted; treat prices as served by TradingView.

## Files

| File | Interval | Bars | First `t` (Unix s) | First (ISO UTC) | Last `t` (Unix s) | Last (ISO UTC) |
|---|---|---:|---:|---|---:|---|
| `MNQ1_15m.csv.gz` | 15m | 5000 | 1782890100 | 2026-07-01T07:15:00Z | 1789516800 | 2026-09-16T00:00:00Z |
| `MNQ1_1h.csv.gz`  | 1h   | 5000 | 1762772400 | 2025-11-10T11:00:00Z | 1789516800 | 2026-09-16T00:00:00Z |
| `MNQ1_4h.csv.gz`  | 4h   | 3000 | 1727906400 | 2024-10-02T22:00:00Z | 1789509600 | 2026-09-15T22:00:00Z |

## Format

Gzipped CSV, header `t,o,h,l,c,v`, one row per bar, sorted ascending by `t`, no duplicate timestamps.

- `t` — Unix seconds, UTC, integer. **Timestamps are bar OPEN times.**
- `o,h,l,c` — prices exactly as returned by the tool (index points, 0.25 tick).
- `v` — volume as returned (contracts).

## Timestamp alignment (as observed)

- 15m and 1h bars open on the plain quarter-hour / hour.
- **4h bars are aligned to the CME Globex session open at 18:00 ET.** Observed bar-open hours in the 4h file are 18:00, 22:00, 02:00, 06:00, 10:00, 14:00 ET on every day. In UTC that is
  - 22:00, 02:00, 06:00, 10:00, 14:00, 18:00 during EDT (UTC-4), and
  - 23:00, 03:00, 07:00, 11:00, 15:00, 19:00 during EST (UTC-5).
  So the UTC clock time of the 4h anchor shifts by one hour across the March/November DST changes; the ET anchor does not.

## Gaps (as observed)

Consecutive-bar spacing is the nominal interval except for gaps that match the CME schedule: the daily 17:00–18:00 ET maintenance halt, weekends (Fri 17:00 ET → Sun 18:00 ET), holiday early closes (13:00 ET) and full-day closures (Christmas, New Year's Day, Good Friday 2025, the 2025-01-09 day of mourning), and the one-hour-shorter/longer weekends around DST changes.

One gap is **not** explained by the exchange schedule: the Thanksgiving-night session of 2025-11-27/28 is missing from roughly 02:00Z to 11:00Z (4h file) / 13:00Z (1h file) on 2025-11-28. This looks like a feed gap rather than a closure. The 15m file does not extend back to that date.

## Last-bar caveat

The fetch happened at ~00:16:40 UTC on 2026-09-16. The final 1h bar (opens 00:00Z, closes 01:00Z) and final 4h bar (opens 2026-09-15 22:00Z, closes 02:00Z) were still forming, and the final 15m bar (00:00Z–00:15Z) had closed only about a minute earlier. Their closes differ slightly across files (29266.25 / 29268.75 / 29276.00), so treat the last row of each file as provisional.

## Verification

Each file was re-read after writing: row count matches the table above, `t` is strictly increasing with zero duplicates, and every row has six columns. To re-check:

```sh
python3 -c "
import gzip,csv
for f in ['MNQ1_15m.csv.gz','MNQ1_1h.csv.gz','MNQ1_4h.csv.gz']:
    with gzip.open(f,'rt') as fh:
        r=csv.reader(fh); next(r); ts=[int(x[0]) for x in r]
    print(f, len(ts), ts[0], ts[-1], all(b>a for a,b in zip(ts,ts[1:])))
"
```
