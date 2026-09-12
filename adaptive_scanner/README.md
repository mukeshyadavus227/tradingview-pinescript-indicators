# Adaptive Scanner Engine

Pine v6 multi-strategy conviction scanner for watchlist deployment, successor to
`Adaptive Swing Scanner v1.0`.

**Status: v3.0.0 — not yet compiled on TradingView.** Paste
`asr_engine.pine` into the Pine editor and compile before deploying. Everything
here is statically checked (delimiter balance, continuation-line indentation,
tuple arity, dead identifiers) but nothing substitutes for the real compiler.

---

## Why this rewrite exists

The audit of v1.0 found three classes of problem. Only the first was visible
from the chart.

**1. The payload never reached the executor.** v1 emitted `scores`, `regime`,
`technicals` and `risk` as nested JSON objects. The `TVSignal` model declares
twelve flat fields and none of those four. Three consequences:

- Stop and target were nested under `"risk"`, while the model reads top-level
  `stop` and `price`, both defaulting to `0.0`. **Orders went out as bare MKT
  with no protective stop.**
- The executor sizes on a `confidence` field (`>=0.8` → 2.0% NAV, `0.6-0.8` →
  1.5%, `<0.6` → 1.0%, reject below 0.3). v1 never emitted it, so every signal
  took the unset default of 1.5%. **The scoring engine had no effect on capital
  at risk.**
- v1's header asserted `sec_type` defaults to `OPT` and the pipeline is
  options-only. The spec says `STK`. That is precisely the vocabulary drift the
  header claimed to prevent.

**2. Correctness bugs.** Listed as `[F1]`–`[F13]` in the script header, each
annotated at its fix site. The three worth knowing about:

- `shortEnabled=false` combined with a higher short score set `bestDirOk=false`
  and **suppressed the whole bar**, discarding a valid long instead of falling
  back to it. Direction filtering now precedes argmax.
- `atrPctile` divided by a hardcoded `252` with no valid-bar guard, understating
  the percentile during warmup and inflating `compositeScore` through the
  `(100 - atrPctile)` term — pushing recently listed symbols to the top of the
  cross-sectional rank.
- `request.security(..., "W", expr)` with no lookahead returns the last
  **confirmed** weekly bar in history but the **forming** one in realtime, so S1
  and S4 disagreed between backtest and live.

**3. Timeframe fragility.** Every lookback in v1 was bar-count based. On a 5m
US-equity chart:

| v1 constant | intended | actual at 5m |
|---|---|---|
| `252` (52wk range, ATR percentile) | 1 year | 3.2 sessions |
| `sma200` | 200 days | 2.6 sessions |
| `roc20` → emitted as `roc_20d` | 20 days | 77 minutes |
| `volSMA20 * close` → `$5M ADV` | 20-day ADV | 100 minutes of volume |
| `cooldownBars = 15` | ~3 weeks daily | 75 minutes |

252 daily bars at 5m would also require 19,656 bars of history, past Pine's
5,000-bar ceiling — several of these were not merely wrong but uncomputable.

---

## Architecture

```
asr_engine.pine      indicator()  — profiles SWING, POSITIONAL
```

Everything with a lookback beyond ~60 trading days comes from a single
tuple-returning `request.security` **daily context** (2 of the 40-call budget
are used in total). Chart-timeframe indicators — ADX, Choppiness, BBW, the EMAs,
RSI — stay on chart bars, because ADX(14) on a 4H chart is a legitimate 4H trend
measure. That split is the whole normalization layer.

The context is always the **last confirmed bar** of the context timeframe. On a
1D chart that means the context is as of yesterday's close. The lag is
deliberate: it is what makes the values identical in backtest and in realtime.

### Scoring rubric

All four sub-strategies spend the same 100 points the same way, and **the
trigger is a boolean gate worth zero points**:

| component | max | question |
|---|---|---|
| trend alignment | 25 | is the higher-timeframe backdrop with us |
| momentum quality | 25 | is the move itself any good |
| volatility / location | 20 | is this a sane place to be entering |
| volume confirmation | 15 | did participation confirm it |
| HTF / regime context | 15 | does the regime favour this style |

v1 handed S2 a flat 30 points for merely breaking the channel plus 10 for any
volume and 5 for any regime — an effective floor of 45 before it demonstrated
anything — while S1 had to earn every point. Comparing those two numbers to pick
a winner, then ranking them cross-sectionally against other symbols, was
comparing different units.

**The weights are still hand-assigned and still unvalidated.** What changed is
that they are now comparable, which is a precondition for the Phase 2
expectancy work, not a substitute for it.

---

## Position sizing is deliberately unchanged

`useScoreConfidence` defaults **OFF**, emitting a constant `0.6` that reproduces
today's flat 1.5%-NAV sizing exactly.

Turning it ON lets a rubric that has never been tested against a single forward
return decide how much money is at risk. Turn it on after Phase 2 produces the
expectancy-by-decile curve, and only if that curve is monotone. If expectancy is
flat across score deciles, the score is noise and the right move is to delete
components, not to size on them.

---

## Profiles (v3)

| | SWING | POSITIONAL |
|---|---|---|
| Entry timeframe | 4H / 1D | 1D |
| Strategies | S1 (trigger ∧ trend ≥ 18), S3 (gate 70), S4 (≥ 75) | S4 (≥ 75) only |
| Selection | priority S1 > S4 > S3 | S4 |
| ATR stop multiple | 1.5 | 2.75 |
| Exit S1 | chandelier 3×ATR from entry, 15-day time stop | — |
| Exit S3/S4 | 50% at +1 R, breakeven, chandelier 3×ATR, no time stop | same |
| Cooldown | 7200 min | 21600 min |
| Positions | one per chart | one per chart |

Why these and not others: `PHASE3_FINDINGS.md`. S2 is gone (no edge). S1 is
SWING-only (loses with wide stops). S3 is off in POSITIONAL (dilutes S4 under
a slot cap). `useRegimeFilter` defaults OFF — the regime is still computed and
emitted as metadata.

`INTRADAY_15M` / `INTRADAY_5M` (Phase 5) and `LONGTERM` are **not** shipped.

## Deployment

1. Paste into the Pine editor, compile, add to chart.
2. Set **Profile** and, if the instrument is not US equity RTH, **Trading
   seconds per session** (23400 = 6.5h RTH, 57600 extended, ~82800 futures).
   The dashboard's `TF norm` row flags a >20% divergence between the formula and
   the observed bars-per-session — if it says `CHECK sessionSec`, every
   day-scaled quantity is wrong.
3. Alert condition: **Any alert() function call**. Leave the message box empty;
   `alert()` supplies the payload.
4. Webhook URL: `https://<host>/webhook?token=<TV_WEBHOOK_TOKEN>` — token in the
   query string, not the body.
5. **Until the server is patched** (`SERVER_PATCH.md` item 9), set *Emit
   SCALE / MODIFY / EXIT events* OFF. Lifecycle payloads carry `action=MANAGE`,
   which the current model rejects — safely, but noisily. ENTRY payloads carry
   the initial stop either way.

**TradingView snapshots the script at alert-creation time.** Any edit to this
file requires re-creating every alert on every symbol. Budget that as real
operational cost. The payload carries `schema_version`, so the server should
reject anything below its floor and make stale alerts fail loudly instead of
trading old logic silently.

### The payload is dual-form

Top-level `stop`, `price`, `strategy` and `comment` are fields the **current**
`TVSignal` model already declares, so the stop and the decision context arrive
intact before the server is patched. `comment` carries a compact digest:

```
ASR2|SWING|BRK|sc=82|cf=0.60|rr=2.4|sl=405.10|tp=426.80|rg=TRENDING|rv=91|cmp=78
```

The nested `thesis` / `desired_state` / `sizing` / `scores` / `regime` /
`context` / `meta` blocks are schema v2 for the patched server. Pydantic's
default `extra='ignore'` means an unpatched server drops them silently rather
than returning 422, so emitting both is safe.

See `SERVER_PATCH.md` for the server-side changes.

---

## Verification

Run these before trusting a signal. Items 3 and 4 are the ones that catch
regressions nothing else will.

1. **Compile.** Pine editor, no errors.
2. **Payload contract.** Fire on a paper symbol; confirm the persisted signal
   file carries a non-zero `stop` and a `comment` starting `ASR2|`.
3. **Timeframe invariance.** Load the same symbol at 15m, 4H and 1D.
   `adv20_usd`, `roc_20d`, `dist_52wk_hi` and `atr_pctile` must agree across all
   three to within rounding. Disagreement means a lookback escaped the context
   layer.
4. **Repaint.** Record the S4 score on a live forming bar, then again after
   confirmation. They must be identical.
5. **`bestDirOk` regression.** Find a historical bar where the short score beats
   the long with shorts disabled. v1 emits nothing; v2 must emit the long.
6. **Warmup.** Load a symbol listed under a year ago. Nothing may fire, and the
   dashboard `BLOCK` row must read `WARMUP`.
7. **R:R gate.** Set Min R:R to 5.0. Signals must stop, and `BLOCK` must read
   `R:R` rather than `SCORE`.

---

## Phase 2 — validation · Phase 3 — exits and rules · Phase 4 — allocation (all done)

`research/` holds the validation harness and its results; `server/` holds the
drop-in modules for the webhook server. Read `PHASE2_FINDINGS.md` (kill/keep),
`PHASE3_FINDINGS.md` (exits, slot cap, deployed v3), `PHASE4_FINDINGS.md`
(cross-profile allocation in % NAV). Phase 2 summary:

- The conviction score predicts outcome for **S4 only** (Spearman +0.063,
  holds out of sample). For S1/S2/S3 it is noise.
- **S1's trigger is the strongest edge in the study** (+0.25 R, n=3,516) and
  the regime gate discarded 99.8% of it — 84% of S1 triggers occur in the
  BREAKOUT regime, which the gate blocks. S1 in an uptrend: +0.47 R.
- **S2 has no edge. Kill.**
- **Half of deployed trades exit on the time stop, and those are the profitable
  ones** (+0.39 R vs +0.15 overall; 43% touched +1 R and gave it back). The
  exit, not the entry, is the biggest lever.
- DSR 0.66–0.79 at the enumerated 56 configurations, 0.22 at an honest N=500;
  PBO 0.06–0.20.

```
research/
  pine_ta.py        exact Pine ta.* reimplementations (RMA seeding, biased stdev, DMI, ...)
  engine.py         Python mirror of asr_engine.pine on daily bars
  labels.py         triple-barrier labels with TradingView's broker-emulator fill rule
  build_events.py   one row per (symbol, bar, strategy, direction) trigger event → out/events_*.csv
  analysis.py       decile curves, walk-forward, regime matrix, ablation, DSR, PBO/CSCV → out/report_*.md
  exit_study.py     14 exit models on every trigger event, train/test split → out/exit_study_*.md
  simulate.py       sequential single-position simulation, v2 vs v3, per-strategy exits → out/phase3_simulation.md
  portfolio_cap.py  slot-capped portfolio admission by priority → out/phase3_slot_cap.md
  variants.py       rule variants under caps (decided POSITIONAL = S4 only) → out/phase3_variants.md
  final_v3.py       deployed v3 (Pine defaults) vs v2, DSR → out/phase3_final.md
  portfolio_sim.py  cross-profile portfolio in % NAV; imports server.allocator → out/phase4_portfolio.md
server/
  schema.py         pydantic models for payload 2.1.0 (superset of v1 TVSignal)
  allocator.py      slot / heat / symbol-uniqueness admission — the same code the simulation validated
  reconciler.py     desired_state vs broker state → minimal order diff, idempotent
  tests/            python -m pytest server/tests
  parity_test.py    Strategy Tester export vs sequential replay — the gate on everything above
  build_twin.py     generates asr_engine_bt.pine from asr_engine.pine (text transform = parity by construction)
  data/             48 symbols × 3000 daily bars (TradingView, split-adjusted)
```

Reproduce: `pip install -r research/requirements.txt && cd research && python build_events.py && python analysis.py && python final_v3.py && python portfolio_sim.py`.
Regenerate the twin after any engine edit: `python research/build_twin.py` (`--check` to verify it is current).

## What is not built yet

The parity gate has not yet been run — it needs a Strategy Tester export from
a TradingView account (`research/parity_test.py` explains how).

Phase 5 adds the intraday profiles (needs S5 ORB, S6 VWAP-reclaim,
time-of-day RVOL), and the LONGTERM profile, Phase 5 the intraday profiles, and a separate
`asr_rotation_403b.pine` handles the retirement sleeve — that one is
cross-sectional over ~20 ETFs and emits portfolio weights rather than per-symbol
entries, so it cannot share this engine's per-chart topology.
