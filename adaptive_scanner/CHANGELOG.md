# Changelog

Every entry that changes emitted values requires re-creating TradingView alerts
on every symbol — TradingView snapshots the script at alert-creation time.
Bump `schema_version` in the payload alongside any such change so the server's
version floor can reject alerts that were not re-created.

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
