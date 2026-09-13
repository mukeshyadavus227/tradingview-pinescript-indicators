# Phase 5 — Intraday profile: evaluated, not shipped

**Verdict: the INTRADAY_15M profile does not ship.** None of the three
intraday constructions shows edge after realistic costs over the data
available, and a random-entry control shows the intraday window itself is
hostile to long-only, flat-by-close trading. `INTRADAY_5M` was never built:
the data source caps at ~2 months of 5m bars, and Part 8 of the original plan
already placed 5m outside Pine's reach (no bid/ask, alert latency, chart caps).

Same discipline as Phases 2–4 — Python mirror first, adversarial review of the
mirror, validation, then a Pine port only if warranted. It was not warranted.

## 1. What was tested

48 US equities/ETFs, 15-minute RTH bars, 2025-12-08 → 2026-09-11 (193
sessions; the source's 5,000-bar ceiling). Train = sessions before
2026-06-15, test = after. Daily context is the prior completed session,
exactly as `request.security("D", expr[1], lookahead_on)` resolves. Costs at
0 / 2 / 5 / 10 bps round trip; headline 5 bps.

| strategy | construction |
|---|---|
| S5 ORB | first close above the 30-minute opening range, cumulative time-of-day RVOL ≥ 1.5, OR width 0.2–1.2 × daily ATR, above daily SMA200, no entries after 12:30 |
| S6 VWAP reclaim | close back above session VWAP after ≥ 2 bars below, above SMA200, time-of-day RVOL ≥ 1 |
| S3i | EMA 9/21 cross on 15m within 3 bars, above VWAP, above SMA200 |

Initial stops: OR opposite edge (S5), below VWAP (S6), 1.5 × ATR15 (S3i);
all floored at 1 × ATR15 and capped at 0.8% of price. Seven exit models,
all flat at the 15:45 close except one hold-overnight variant. 22,830
trigger events.

## 2. Results — eligible events, 5 bps, fixed-2R / EOD-flat exit

| | n train | mean R train | n test | mean R test | hit test | PF test |
|---|---:|---:|---:|---:|---:|---:|
| S5 ORB | 215 | +0.038 | 70 | −0.370 | 24% | 0.42 |
| S6 VWAP reclaim | 1,634 | −0.078 | 623 | −0.230 | 36% | 0.62 |
| S3i EMA cross | 5,740 | −0.044 | 2,539 | −0.332 | 32% | 0.45 |
| **random-entry control** (same slots, same geometry, same exit) | 12,972 | **−0.109** | 6,228 | **−0.197** | 39% | |

Gross of costs the three are approximately zero (S5 +0.03, S6 −0.01, S3i
−0.03 R); 5 bps turns zero into loss. The control is the important row:
a random long at a random eligible bar loses 0.10–0.19 R, because
open-to-close drift in this window is negative (SPY +1.6% over the test
period, all of it overnight; mean open→close −0.04%, 44% up-days) and the
EOD flat forgoes the overnight premium every day.

**Alpha relative to the control:** S5 +0.15 R in train, −0.17 R in test
(n = 70 — not a result, a coin). S6 +0.03 / −0.03. S3i +0.07 / −0.14.
Nothing stable.

**Exit models:** every EOD-flat variant is within noise of the others.
Holding overnight (partial + 2×ATR trail, no flat) is the best exit for S6
and S3i in test (−0.22 / −0.19 R) — it recovers some overnight drift — and
still loses.

**Conditioning:** no bucket with n ≥ 200 is meaningfully positive. S5 with
cumulative RVOL 1.8–3 is +0.04 (n = 206); S5 *below* the 200-day SMA is +0.03
(n = 824) — the opposite of the trend gate the design assumed, and still not
a number to trade on.

## 3. Why this is a kill and not a "needs more data"

The burden is on the strategy. Over 193 sessions × 48 names, three
reasonable constructions produced no after-cost edge and no edge over a
random-entry control, in either half of the window. A multi-year dataset
could in principle reverse that — this window is one regime, with a
negative-drift test half — but the honest reading of what is available is
that long-only intraday breakouts and reclaims on liquid US names, flat by
the close, pay costs and forgo the overnight premium for nothing in return.
Shipping a Pine profile for it would be building infrastructure ahead of
evidence, which is exactly what Phase 2 was set up to prevent.

What *would* change the verdict: (a) multi-year 15m data showing S5's train
alpha persists across regimes; (b) a construction that keeps the overnight
premium — intraday triggers as **entry timing for the SWING profile**, held
under the v3 exit engine. The second is the more promising and is a
different product: an entry-quality improvement to a validated system, not
a new profile. It is the candidate for Phase 6.

## 4. What ships from Phase 5

- `research/engine_intraday.py` — the mirror (session slots, prior-session
  daily context, time-of-day RVOL updated after use, session VWAP + bands,
  once-per-day OR latch, capped stops). Reviewed by an adversarial workflow
  for leakage, session handling and Pine portability; findings recorded in
  §5.
- `research/intraday_study.py`, `intraday_sim.py`, `intraday_baseline.py`,
  `labels.py` (EOD-flat labeller, intraday exit models).
- `research/data_15m/` — 48 symbols × 5,000 15m bars, gzipped (3.6 MB), so
  the study is reproducible.
- `research/out/phase5_intraday.md` — full tables.
- No Pine changes beyond a header note recording the decision.

## 5. Mirror review

An adversarial workflow read `engine_intraday.py` through three lenses
(look-ahead leakage, session/time handling, Pine portability); every
candidate was then attacked by two independent skeptics told to refute it.
41 agents. 19 candidates → 13 confirmed, 1 contested, 5 refuted. The
verifiers reproduced each confirmed finding numerically against the files.

**Leakage: none.** The engine's arrays are causal (verified by prefix
truncation: every column except the EOD-flat index is identical for bars up
to a cut). The daily-context mapping was confirmed to deliver the prior
completed session in 9,264 of 9,264 symbol-sessions; one latent staleness
mode (a missing daily row, or a live loader that omits today's row, made the
context one session *older*, never newer) was fixed by mapping each session
to the last daily row strictly before it.

**Session handling — fixed:**
- *Major.* Absolute entry cutoffs let a half-day admit a trade on its final
  bars and hold it overnight. Entries are now gated relative to the session
  end (≥ 3 bars left).
- Opening range initialised to ±inf, so a session missing its first bars
  would "break out" over a sentinel; now NaN unless every OR bar was seen.
- The S3i "cross within 3 bars" window spanned the overnight gap; the cross
  must now be in the current session.
- Session RS anchored the symbol on its open and SPY on its first close; both
  now use the open.
- A short session's closing auction contaminated the per-slot volume EWMA for
  ~10 sessions; short sessions no longer update the averages.
- A slot-range assertion so an extended-hours feed fails loudly.

**Contested (1):** the EOD-flat index is derived from later bars. It is a
label rule ("flat at the session's last bar"), causal at that bar and
expressible in Pine via the session calendar; left as is, documented.

**Effect on the results:** S5 train +0.065 → +0.038 (n 247 → 215); every
other cell moved by < 0.01 R; the control is unchanged. The verdict does not
depend on any of it.

**Pine portability (had the profile shipped):** session VWAP + stdev bands
map to `ta.vwap(hlc3, timeframe.change("1D"), 1)`; the time-of-day EWMA is a
`var` array indexed by slot, read then updated on `barstate.isconfirmed`,
with a per-slot observation count replacing the 60-bar warm gate; the OR
latch must consume on the raw break, not the gated one; session RS needs
`request.security("SPY", timeframe.period, open)` latched on the new day.
None of this was built.
