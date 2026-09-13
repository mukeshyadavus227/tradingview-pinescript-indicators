# Changelog

Every entry that changes emitted values requires re-creating TradingView alerts
on every symbol — TradingView snapshots the script at alert-creation time.
Bump `schema_version` in the payload alongside any such change so the server's
version floor can reject alerts that were not re-created.

## 3.1.2 — Phase 6: entry timing decided; no intraday trigger

No change to emitted values. No alert re-creation needed. The fill rule is a
server-side decision (`SERVER_PATCH.md` item 11).

### Added (research only)
- `research/phase6_entry_timing.py` — daily SWING signals re-filled under eight
  intraday entry rules (next open, next close, opening-range break, VWAP
  confirmation, pullback limits, limit-then-MOC) with the fill session
  collapsed into a partial daily bar and the v3 exit engine run from there.
- `research/phase6_fill_baseline.py` and `simulate.simulate_symbol(fill=)` —
  the deployed profiles over twelve years with a next-open fill.

### Findings (PHASE6_FINDINGS.md)
- Opening-range and VWAP confirmation lose 0.16–0.17 R per trade to a plain
  next-open fill on identical signals (95% CI excludes zero). Pullback limits
  improve the trades they fill and miss the winners; per signal no better
  than the open. Nothing ships.
- The Phase 2–4 close-fill convention overstated the deployable edge by
  −0.02 R per trade (SWING) and −0.01 R (POSITIONAL) over twelve years; by
  −0.14 R in the 2025-12 → 2026-09 window. Fill rule fixed as market-on-open
  next session against the absolute stop. README numbers are now the
  next-open numbers.

## 3.1.1 — Phase 5: intraday profile evaluated and not shipped

No change to emitted values. Pine header records the decision. No alert
re-creation needed.

### Added (research only)
- `research/engine_intraday.py` — INTRADAY_15M mirror, adversarially reviewed.
- `research/intraday_study.py`, `intraday_sim.py`, `intraday_baseline.py`,
  intraday exit models and EOD-flat labelling in `labels.py`.
- `research/data_15m/` — 48 symbols × 5,000 15m RTH bars (gzipped).

### Findings (PHASE5_FINDINGS.md)
- S5 ORB, S6 VWAP reclaim and S3i EMA cross: ~zero gross, negative after
  5 bps, no stable alpha over a random-entry control in either half of the
  window. Holding overnight helps and still loses. Not shipped.
- INTRADAY_5M never built: 2 months of data, and outside Pine's reach.

## 3.1.0 — Phase 4: cross-profile allocation and server modules

No change to the Pine or to emitted values. No alert re-creation needed.

### Added
- `server/schema.py`, `server/allocator.py`, `server/reconciler.py` with
  tests (21 passing). The allocator is imported by
  `research/portfolio_sim.py`, so the admission rule validated in research and
  the rule the server runs are the same code; a replay test asserts it.
- `research/portfolio_sim.py` — SWING v3 + POSITIONAL v3 candidates through a
  shared slot budget, sized as a fraction of current equity, reported in % NAV.

### Findings (PHASE4_FINDINGS.md)
- One open position per symbol across profiles is the rule that matters
  (Sharpe 0.81 → 1.32 at cap 10). Arrival order ≈ per-bar tiebreak; priority
  by per-trade expectancy is wrong under a shared cap; reserving slots per
  profile minimises drawdown and costs a third of the return.
- POSITIONAL adds nothing to a shared cap-10 book; on its own capital it is a
  half-return / half-vol / same-Sharpe product. Separate sleeve or don't run.
- Ten slots at 1% risk (10% heat) is the configuration. Five slots collapse
  under the heat cap; 1.5% risk buys a third more return for a −40% all-period
  drawdown bound.

## 3.0.0 — Phase 3: exit engine, validated rules

**Alerts must be re-created.** Payload schema 2.1.0.

### Changed
- **Exit engine.** The indicator carries the position it last entered and
  manages it bar by bar with the validation labeller's fill rules. S1: chandelier
  3×ATR from entry, profile time stop. S3/S4: 50% at +1 R, breakeven, chandelier
  3×ATR on the remainder, no time stop. Selected on 2015–20, confirmed 2021+.
- **Payload.** One `alert()` per bar carrying `events[]` (ENTRY / SCALE /
  MODIFY / EXIT / HEARTBEAT) and a live `desired_state`. Lifecycle events use
  `action=MANAGE`; the unpatched server rejects them safely. `emitLifecycle`
  and `emitHeartbeat` inputs.
- **S1** fires on trigger ∧ own trend component ≥ 18; no regime gate, no score
  threshold; SWING only.
- **S3** gated at score ≥ 70 as a slot-cap rate limiter (not a predictor); off
  in POSITIONAL by default.
- **S4** unchanged at ≥ 75.
- **Winner** = highest-priority eligible strategy (S1 > S4 > S3), long-only.
- `useRegimeFilter` default OFF; regime still emitted.
- One position per chart; `fireSignal` requires flat.
- Twin execution block: partial-leg + remainder exits re-issued from the
  engine's working stop; S1 time stop; resync guard.

### Removed
- S2 Donchian Breakout (no edge; CI spans zero).
- Reference-line "last emitted" visualisation; replaced by live engine plots.
- `Min Conviction Score` master input (per-strategy gates replace it).

### Results (cap 10, test 2021+, see PHASE3_FINDINGS.md)
- SWING: Sharpe 0.69 → 1.21, R/trade +0.09 → +0.22, max DD −22.5 → −19.1 R.
- POSITIONAL (S4 only): Sharpe 1.10 → 1.27, max DD −21.5 → −10.9 R, capacity
  +13.5 → +9.0 R/yr.

## 2.0.0-phase2 — validation harness and findings

No change to emitted values except the R:R fix below. **Alerts must be re-created
for the R:R fix.**

### Added
- `asr_engine_bt.pine` — `strategy()` twin, generated from the indicator by
  `research/build_twin.py` so the math is the same text.
- `research/` — Python mirror, labeller, event builder, analysis, parity test,
  48-symbol daily dataset. See `PHASE2_FINDINGS.md`.

### Fixed (found by the harness)
- **R:R gate was structurally incompatible with the strategies' own geometry.**
  SWING's 2.0 gate excluded S3 (designed 1.67) and S4 (1.6) outright — SPY had
  one signal in twelve years. POSITIONAL scaled the stop without the target,
  pushing S3 to 0.9. Gate default is now 1.5 for both profiles and the target
  scales with the profile alongside the stop.

### Findings (see PHASE2_FINDINGS.md for the numbers)
- Score predicts outcome for S4 only. S1/S2/S3 scores are noise.
- S1's regime gate discards 99.8% of the study's strongest trigger edge.
- S2 has no edge.
- Time-stop exits are the profitable ones; exit design is the largest lever.

## 2.0.0-phase1 — Adaptive Scanner Engine

Rewrite of `Adaptive Swing Scanner v1.0`. Phase 1 of the plan: correctness and
payload repair only. **Alerts must be re-created.**

### Fixed

- **F1** Payload reached the server stripped. Stop, target, scores and regime
  were nested in objects `TVSignal` does not declare, so orders went out as bare
  MKT with `stop=0.0`. Now written to top-level fields the current model accepts,
  plus schema v2 blocks for the patched server.
- **F2** `confidence` was never emitted, so the executor sized every signal at
  its 1.5%-NAV default and the scoring engine had no effect on capital at risk.
  Now emitted, defaulting to a constant that reproduces current sizing exactly.
- **F3** `shortEnabled=false` with a higher short score suppressed the entire
  bar instead of falling back to the long. Direction filtering now precedes
  argmax.
- **F4** `atrPctile` divided by a hardcoded 252 with no valid-bar guard.
- **F5** HTF repaint: `request.security` without lookahead returned the forming
  bar in realtime and the confirmed one in history. Now `expr[1]` +
  `lookahead_on` in both the daily and weekly contexts.
- **F6** No warmup gate; the script emitted confident output from bar 1.
- **F7** `rrRatio` was computed and never enforced.
- **F8** Stop/target prices were not rounded to `syminfo.mintick`; rounding now
  happens before the R:R gate so the gate tests the price actually worked.
- **F9** Score incomparability: S2 received a 30-point base for merely
  triggering. All four strategies rewritten against one rubric with the trigger
  as a zero-point boolean gate.
- **F10** Day-scale features moved to a daily `request.security` context, so
  `roc_20d` means 20 days on every timeframe rather than 77 minutes on 5m.
- **F11** Fictional position tracking and its same-bar SL/TP ambiguity removed;
  the engine now reports only what it last emitted, labelled as chart reference.
- **F12** Hardcoded `hour == 13` gate replaced with a session-relative gate.
- **F13** Cooldown moved from bars to wall-clock minutes.

### Also fixed during implementation

- Ternary over a tuple in the context selection — a compile error, not a
  behavioural bug. Replaced with context-timeframe selection so there is one
  code path and the engine never requests a timeframe lower than the chart's
  (which with `lookahead_on` would be genuine forward-looking bias).
- Secondary-regime identification used float equality on computed sums; now
  ranked.
- Comma-separated variable declarations, which Pine does not support.
- ATR percentile now ranks the previous bar's ATR directly rather than taking a
  history reference on a loop-derived function local.

### Known limitations

- **Not compiled on TradingView.** Statically checked only.
- Rubric weights remain hand-assigned and unvalidated. Phase 2 blocks on the
  expectancy-by-decile curve per strategy per regime.
- `rvPctile` is not time-of-day normalized and is meaningless on intraday
  charts. The Phase 5 intraday profile replaces it.
- No earnings blackout — it belongs server-side, since Pine cannot see the
  forward earnings calendar reliably.
- No exit, trail or time-stop signals are emitted yet; `desired_state` carries
  the intended levels but the heartbeat mechanism is Phase 4.
