# Phase 6 — Entry timing: intraday triggers for the SWING profile

**Verdict: no intraday trigger ships. The deployed fill rule is market-on-open
the session after the daily signal, against the engine's absolute stop.** The
15m triggers Phase 5 left open (opening-range break, VWAP confirmation) lose
to a plain next-open fill on identical signals, and the loss is outside the
bootstrap interval. Pullback limits improve the trades they fill and forfeit
the ones they miss; per signal they are no better than the open.

The more consequential result is the one this phase was not asked for: every
Phase 2–4 number assumed a fill at the signal close, which a daily-close
webhook cannot get. Re-run over twelve years with the fill it can get, the
deployed profiles survive intact (SWING −0.02 R per trade, POSITIONAL
−0.01 R). The 2025-12 → 2026-09 window used for the intraday study was the
worst fill regime in the twelve years (−0.14 R per trade), which makes it
the most favourable possible test for "wait for a better price" — and the
triggers still lost.

## 1. What was tested

**Signals.** The deployed v3 SWING profile (Pine defaults, sequential
one-position-per-chart, `EXITS_V3`), 48 symbols. Each signal is a daily bar D
with the engine's own entry reference (close), stop and target. The stop and
target are kept as **absolute prices** under every rule — that is what the
server places against whatever fill it gets. A robustness pass re-anchors the
same stop distance to the fill.

**Fill rules on the 15m RTH bars of D+1 (or later where stated):**

| rule | fill |
|---|---|
| close_D | the signal close — the Phase 2–4 harness convention; **not executable live** |
| open_D1 | market-on-open next session |
| close_D1 | market-on-close next session |
| orb | first 15m close above the 30-minute opening-range high, 10:00–12:30, within 3 sessions; else no trade |
| vwap_conf | first 15m close (≥ 10:00) above session VWAP **and** above the signal close, within 3 sessions; else no trade |
| limit_close | resting day limit at the signal close (fills at the open if the open is lower, else on touch); else no trade |
| limit_atr | resting day limit at signal close − 0.25 × daily ATR; else no trade |
| limit_or_moc | limit_close, falling back to market-on-close D+1 if unfilled |

**Path after the fill.** The fill session's remaining 15m bars collapse into a
partial daily bar (open = fill; high/low from the bars after a close-fill, or
from the fill bar onward for a touch-fill — the conservative ordering), then
the validated daily exit engine (`labels.label_event_v3`) runs on daily bars
exactly as in Phase 3. 3 bps per leg. Paired comparison on identical signals,
bootstrap 95% intervals on the paired difference.

**Sample.** 167 sequential signals (466 overlapping eligible bars) over 193
sessions, 2025-12-04 → 2026-09-11. One regime; not a walk-forward. The
fill-rule baseline (§3) is the twelve-year check.

Script: `research/phase6_entry_timing.py` → `research/out/phase6_entry_timing.md`.

## 2. Results — intraday timing (n = 167, stop anchored at the signal)

| rule | fill % | mean R (filled) | mean R per signal | median fill vs signal (ATR) | Δ vs open_D1, paired [95% CI] |
|---|---:|---:|---:|---:|---|
| close_D (not executable) | 100% | +0.458 | +0.458 | 0.00 | +0.124 [+0.04, +0.21] |
| **open_D1** | 99% | +0.343 | +0.341 | +0.08 | — |
| close_D1 | 99% | +0.310 | +0.306 | +0.22 | −0.041 [−0.14, +0.06] |
| orb | 83% | +0.279 | +0.232 | +0.48 | **−0.168 [−0.28, −0.06]** |
| vwap_conf | 87% | +0.288 | +0.252 | +0.37 | **−0.160 [−0.24, −0.08]** |
| limit_close | 72% | +0.411 | +0.298 | −0.04 | +0.072 [+0.02, +0.13] on the 72% filled |
| limit_atr | 49% | +0.475 | +0.230 | −0.25 | +0.217 [+0.12, +0.34] on the 49% filled |
| limit_or_moc | 99% | +0.356 | +0.354 | 0.00 | +0.014 [−0.04, +0.06] |

Reading it:

- **The triggers select correctly and pay too much for it.** The signals ORB
  skips would have earned −0.19 R at the open; the ones VWAP-confirmation skips,
  −0.45 R. That is real information. But the trigger fills 0.4–0.5 ATR above
  the signal close, the absolute stop is now 1.25× further away in R terms,
  and the taken trades earn +0.28 R instead of +0.45 R at the open. Net: −0.16
  to −0.17 R per filled trade, interval excludes zero. Re-anchoring the stop to
  the fill does not rescue it (−0.15 to −0.19 R).
- **Pullback limits are the mirror image.** They improve the filled trades
  (+0.07 R at the signal close, +0.22 R a quarter-ATR lower) because the
  absolute stop is nearer and the geometry better — and they miss the signals
  that never come back, which are winners (+0.35 R and +0.42 R at the open).
  Per signal, `limit_close` is +0.298 against the open's +0.341 and
  `limit_atr` is +0.230. Momentum entries that pull back are the weaker ones;
  the pullback filter is a negative selection on this profile.
- **Limit-then-MOC is the open with extra steps.** +0.354 vs +0.341 per
  signal, paired +0.014 [−0.04, +0.06]; −0.013 on the overlapping set. Not
  distinguishable, and it adds an order-management branch to the server.
- **By strategy** (filled mean R, open_D1): S1 +0.87 (n = 15), S3 +0.31
  (n = 111), S4 +0.25 (n = 40). S1 prefers the D+1 close (+1.31) on 15 trades;
  that is noise at this n and is not acted on.
- **Costs** move every rule by the same ~0.02 R from 3 to 10 bps and change no
  ordering.

Robustness (same report): re-anchored stops and the 466-signal overlapping set
give the same ordering — ORB and VWAP confirmation below the open by a margin
whose interval excludes zero, limits above on the filled subset and at or below
per signal.

## 3. The deployable baseline (twelve years, daily bars)

`research/phase6_fill_baseline.py` re-runs the deployed profiles with a fill at
the next session's open (the daily bar's open is the fill, the full session is
the path) against the absolute stop. Same trade generation as
`phase3_final.md`.

| profile, cap 10 | fill | trades | mean R | SR ann | R per year | max DD (R) |
|---|---|---:|---:|---:|---:|---:|
| SWING | close (harness) | 1,179 | +0.215 | +1.12 | +22.9 | −27.3 |
| SWING | **next open** | 1,138 | +0.220 | +1.12 | +22.6 | −21.5 |
| POSITIONAL | close (harness) | 383 | +0.301 | +1.36 | +10.4 | −10.9 |
| POSITIONAL | **next open** | 347 | +0.272 | +1.23 | +8.6 | −11.5 |

Paired next-open minus close on identical signals, uncapped: SWING −0.022 R
(n = 2,204, 95% CI [−0.046, +0.001]); POSITIONAL −0.008 R (n = 571,
[−0.035, +0.020]). By strategy the cost sits on S1 (−0.11 R: mean-reversion
entries gap against you overnight) and is negligible for S3/S4 (−0.02 R).

DSR at cap 10 for the next-open fill: SWING 0.56 / 0.27 / 0.12 and POSITIONAL
0.68 / 0.42 / 0.24 at N = 100 / 500 / 2000 trials — within a few hundredths of
the Phase 3 values. MinTRL 24–25 months either way.

**By year, SWING paired haircut (R per trade):** 2015 −0.01, 2016 +0.02,
2017 +0.04, 2018 0.00, 2019 −0.14, 2020 +0.02, 2021 −0.01, 2022 −0.02,
2023 +0.03, 2024 −0.04, 2025 −0.01, **2026 −0.15**. The intraday study's
window is one of the two worst fill years in the sample. The −0.124 R
"cost of the open" in §2 is that window, not the system.

## 4. Decisions

1. **Fill rule: market-on-open, next session, absolute stop.** Written into
   `SERVER_PATCH.md` item 11. The Pine already emits at the daily close and
   nothing about the payload changes; the server's staleness window for
   daily-close signals must extend to the next open (item 6 already says so).
2. **No 15m entry trigger, no pullback limit, no limit-then-MOC.** None beats
   the open per signal; two lose with intervals that exclude zero. The
   INTRADAY profiles stay unshipped, and the last intraday construction the
   plan left open is closed.
3. **The reported edge for the deployed profiles is the next-open row above,
   not the Phase 3 close-fill row.** README updated. The difference is small
   over twelve years; it was not small in the last nine months, and a live
   fill log against the signal close is the monitoring that catches it if it
   persists (signal-density canary plus a fill-slippage canary, both in ATR).

## 5. What would change the verdict

- A fill-slippage log from live trading showing the 2026 gap regime persisting
  (> 0.1 ATR median overnight slip for two consecutive quarters). Then the
  candidates are the pullback limit for S3 (its best sub-case) and a
  gap-conditioned rule (skip or limit when the open gaps > 0.5 ATR), neither
  of which this sample can validate.
- Two more years of 15m history. The source caps at 5,000 bars; a different
  feed is needed for a walk-forward on any intraday rule.
