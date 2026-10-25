# Changelog

All notable changes to the MNQ MTF Swing engine.

**Process rule, inherited from `adaptive_scanner/CHANGELOG.md`:** TradingView
snapshots a script when an alert is created, so any entry below that changes an
emitted value or a rule requires **re-creating every alert on every chart**.
Budget that as real operational cost.

## [1.0.0] — 2026-09-16

First version. Long-only MNQ swing engine on a 15M chart with a strict
4H → 1H → 15M hierarchy, plus the research harness that defines it.

### Added

- `mnq_mtf_swing.pine` — the indicator. Two tuple-returning `request.security`
  calls (240 and 60) with every element at offset `[1]` and `lookahead_on`;
  pivot rings maintained in the chart context; a five-state 15M trigger; entry
  triangle, SL and TP lines with a per-entry label; a dashboard whose BLOCK row
  names the single gate holding a signal back; Entry / SL / TP alerts carrying
  SignalStack payloads.
- `mnq_mtf_swing_bt.pine` — strategy twin, generated from the indicator by text
  transform so the two cannot drift.
- `research/engine.py` — the rules in executable Python; the Pine is a port of
  it, and it is the tiebreaker if they disagree.
- `research/bars.py` — 15M → 1H/4H aggregation anchored to the 18:00 ET session
  open, proven equal to TradingView's own 1h/4h bars on the committed sample.
- `research/ta.py` — EMA/ATR with Pine's seeding rules and an explicit pivot
  definition (strictly above the left window, at or above the right, confirmed
  R bars later) used instead of `ta.pivothigh`, whose tie handling is not
  documented.
- `research/build_twin.py`, `research/pine_lint.py`, `research/tests/` (29
  tests), `research/data/` (MNQ 15m/1h/4h sample bars).

### Decided while building

- **Entry-session filter defaults OFF.** With an RTH window, every one of 22
  breaks in the sample was deferred. This is a swing engine on a 23-hour
  contract held overnight, so a 03:00 break is as valid as a 10:00 one. Entries
  into the 16:00-17:00 CT halt are still deferred.
- **The stop is the 15M higher low**, with the 1H zone floor as the fallback
  only when the higher-low stop is tighter than the noise floor. The first draft
  had it the other way round; that fired on almost every setup and the risk cap
  then killed 5 of 9 breaks.
- **"No immediate strong resistance" is enforced in the target scan**, not as a
  separate 4H gate, so it blocks a trade where that has a consequence instead of
  adding a second tolerance parameter measuring the same thing.
- **Volume contraction is reported, not required**, as asked, and because
  TradingView and broker feeds report different futures volume.
- **Stop wins** when a bar touches both levels — conservative, and a deliberate
  divergence from `adaptive_scanner/research/labels.py`.

### Fixed before first release, from two independent review passes

- **`ta.ema` was handed a `series int` length.** A user-function parameter
  declared with a bare type name arrives as `series`, losing the input's
  `simple` qualifier, and `ta.ema` requires `simple int`. The context functions
  now take `simple int`, as `adaptive_scanner/asr_engine.pine` does. This was a
  compile error, not a style point.
- **A roll-window exit sent no alert**, so the script went flat internally and
  stopped watching the levels while the broker position stayed open with
  nothing left to close it.
- **Zone candidates collapsed to the wrong price.** Walking them in priority
  order kept the higher-priority level's own price rather than the cluster's
  lowest, putting the zone, the invalidation and the fallback stop up to a full
  tolerance too high.
- **Target levels did not merge**, so a weak 1H high sitting just under a 4H
  wall stopped vetoing the trade and the scan stepped over it to the wall.
- **The roll window ended at 00:15 on expiry day**, because it compared a
  timestamp against midnight instead of comparing dates.
- Three `array.get` calls relied on `and` short-circuiting to stay in bounds,
  one loop would have counted downward past the end of a single-element array,
  and a float equality was used to de-duplicate the 24-hour high.

### Known limitations

- Not compiled on TradingView, and not validated. 5 trades on 2.5 months of 15M
  bars is a plausibility check, not evidence. See README *What still has to be
  proven*.
- SignalStack has no bracket field, so the SL and TP alerts are the exits; a
  missed alert leaves the position unprotected at the broker.
- The exit action is broker-dependent: Tradovate documents only `buy`/`sell`,
  where a `sell` while flat opens a short.
- On a continuous chart the quarterly roll puts a basis jump into the series.
  Entries stop `rollDays` before expiry and an open position is closed, but the
  higher-timeframe pivots still straddle the roll for a week or two.
