# Phase 2 — Validation findings and kill/keep decisions

**Setup.** 48 US equities/ETFs, daily bars 2014-10 → 2026-09 (11.1 years of
evaluable signals after warmup), Python mirror of `asr_engine.pine` with
TradingView's broker-emulator fill rule, triple-barrier labels using each
strategy's own stop/target geometry and the profile's time stop. R is in units
of initial risk (entry-to-stop); headline numbers are net of 3 bps round trip.
Reports: `research/out/report_SWING.md`, `research/out/report_POSITIONAL.md`.

**Two caveats that bound every number below.** The universe is today's liquid
survivors, so absolute long-side expectancies are optimistic; the *relative*
comparisons (score vs. no score, S1 vs. S4) are far less affected. And the
Pine↔Python parity gate has not yet been run — it needs a Strategy Tester
export from your TradingView account (`research/parity_test.py`). The mirror
is faithful by construction, not yet proven.

---

## The answer to the question Phase 2 was asked

**Does the conviction score predict outcome?** For three of four strategies,
no. For S4, weakly and out-of-sample, yes.

| strategy | Spearman(score, R) | decile monotonicity | OOS ρ (3y/1y rolling) | deployed vs. all-triggers | verdict on the score |
|---|---:|---:|---:|---|---|
| S1 MeanRev | −0.013 (p=0.44) | +0.10 | −0.001 | 7 trades vs. 3,516 at +0.25 | **noise** |
| S2 Breakout | −0.039 (p=0.39) | −0.43 | −0.004 | 33 at +0.02 vs. 491 at +0.08 | **noise** |
| S3 Momentum | +0.015 (p=0.05) | +0.35 | +0.002 | 1,081 at +0.14 vs. 16,762 at +0.15 | **noise** — statistically nonzero at n=16K, economically zero |
| S4 MTF | +0.063 (p=2e-8) | +0.55 | +0.046 | 422 at +0.19 vs. 8,006 at +0.13 | **weak, real, holds OOS** |

The S3 row is the one to sit with. Its trigger — a fast/slow EMA cross within
five bars, not overbought — carries the entire edge: +0.145 R across 16,762
events with a 95% CI of [+0.13, +0.16]. Adding the alignment filter moves that
to +0.155. Adding the score threshold moves it to +0.149. Deploying moves it to
+0.141. Every layer of the rubric on top of the trigger is decoration. The
top score decile (+0.133) is *worse* than the fifth (+0.232).

---

## Kill / keep

### S1 RSI Mean Reversion — KEEP the trigger, KILL the regime gate, KILL the score

The trigger (RSI < 30 within 1.5 ATR of the 20-bar low) is the strongest raw
edge in the study: +0.248 R over 3,516 events, PF 1.44, CI [+0.20, +0.30].
The deployed system fired it **7 times in eleven years across 48 names.**

The cause is structural, not a threshold. 84% of S1's triggers occur while the
regime detector reads BREAKOUT, because an RSI<30 print near a 20-bar low *is*
an ATR/BBW expansion event by that detector's definition. The MEAN_REV regime
that S1 is "aligned" to occurred 15 times. The gate meant to keep S1 in its
home regime keeps it out of the only regime where it ever fires.

The rubric's own `trend` component does what the gate was meant to do:

| S1 population | n | mean R | hit |
|---|---:|---:|---:|
| all triggers | 3,516 | +0.248 | 46.9% |
| trend component ≥ 18 (above SMA200, SMA50 > SMA200) | 435 | **+0.470** | 53.8% |
| trend component = 0 | 3,081 | +0.217 | 46.0% |

Buying oversold pullbacks near support in a confirmed uptrend is the best cell
in the entire validation. Phase 3 change: S1 fires on trigger ∧ `trend ≥ 18`,
no regime alignment, no score threshold. Expect ~0.8 signals per symbol-year.

### S2 Donchian Breakout — KILL

No edge in the trigger: +0.078 R, CI [−0.08, +0.23], across 491 events. Hit
rate 36%, 62% of exits are stops. The "not extended beyond SMA50 + 1.5 ATR"
filter removes 90% of channel breaks on any instrument in a trend (on SPY: 414
twenty-day-high closes → 39 not extended → 3 with volume), so what survives
is the breakouts that *failed to trend*, which is why they stop out. Remove it
from the engine. If breakout is wanted later it needs a different construction
(base-length and contraction, the S8 idea from the plan), not this one.

### S3 EMA Momentum — KEEP the trigger, KILL the score as a filter

Trigger edge is real and tight (+0.145, n=16,762). The problem is density:
~31 triggers per symbol-year is far too many to trade, and the score does not
tell you which to take. Neither does regime — NEUTRAL +0.15, MOMENTUM +0.20,
TRENDING −0.11 (n=56, inconclusive). What the score *can* still do is
tie-break across symbols server-side, where the pipeline already ranks
cross-sectionally. Phase 3 change: S3 emits on trigger with the score attached
as metadata; the server's cross-sectional rank (composite, relative strength)
chooses among simultaneous S3 candidates. The engine stops pretending the
score is a gate.

### S4 Multi-TF Trend — KEEP, and it is the only place the rubric earns its keep

Deployed +0.193 R (SWING) / +0.340 (POSITIONAL, PF 2.23, 61.5% hit). The score
threshold sweep is monotone up to 75 and then degrades:

| S4 score ≥ | n | mean R | per symbol-year |
|---:|---:|---:|---:|
| 0 | 8,006 | +0.132 | 15.0 |
| 60 | 4,743 | +0.175 | 8.9 |
| 70 | 2,155 | +0.193 | 4.0 |
| 75 | 1,261 | +0.211 | 2.4 |
| 80 | 644 | +0.157 | 1.2 |

Keep the default at 75 for SWING; do not raise it. Component ablation shows
`loc` (pullback depth + sane ATR percentile) and `trend` carry the signal;
`vol` and `htf` contribute little. S4 in TRENDING regime is +0.26 (SWING) /
+0.49 (POSITIONAL) at n=129 — the one regime cell where the detector adds value.

### Regime detector — DEMOTE from gate to metadata

Its MEAN_REV state is nearly unreachable (15 S1-coincident bars in 11 years);
TRENDING is 3.5% of bars; BREAKOUT is really "volatility expanding" and fires
30% of the time. As a *gate* it destroyed S1 and added +0.01 R to S3. As
*metadata* it has one demonstrated use (S4 in TRENDING). Phase 3: keep
computing it, keep emitting it, stop gating on it. `useRegimeFilter` defaults
to OFF.

### Shorts — stay OFF

Every strategy's short trigger is negative: S1 −0.19, S2 −0.19, S3 −0.12, S4
−0.15 R, all with CIs excluding zero. Some of that is eleven years of
survivor-universe bull market. None of it is an argument for enabling them on
equities without a bear-regime gate that does not yet exist.

---

## The finding that matters more than any entry rule

**Half of all deployed trades exit on the time stop, and those are the good
ones.** SWING: 51% TIME exits at +0.39 R mean, versus +0.15 for the set
overall. Mean MFE of a TIME exit is +0.93 R; 43% of them touched +1 R at some
point and gave it back. POSITIONAL: 41% TIME exits at +0.40 R, 46% touched +1 R.

The 3.0 / 4.0 ATR targets are too far for the horizons, and the fixed stop
gives back excursion that a trail would keep. The single highest-expectancy
change available is not an entry tweak — it is the exit: partial at +1 R,
stop to breakeven, chandelier trail on the remainder. That is Phase 4 in the
plan; the data says pull it forward ahead of Phase 3's LONGTERM profile.

POSITIONAL beats SWING on every strategy (+0.27 vs +0.15 overall) for the same
reason: the longer horizon lets the trend component work.

---

## Multiple-testing and cost

| | SWING | POSITIONAL |
|---|---:|---:|
| Deployed monthly Sharpe (sum of R per month) | +0.32 | +0.46 |
| DSR at N = 56 (configurations this harness enumerated) | 0.66 | 0.79 |
| DSR at N = 500 (honest allowance for years of hand-tuning) | 0.22 | 0.23 |
| PBO via CSCV, 56 configs, S=16 | 0.20 | 0.06 |
| Mean R at 0 → 10 bps round trip | +0.158 → +0.131 | +0.276 → +0.261 |

Read together: the configuration family is not badly overfit (PBO well under
0.5 — the ranking S4 > S3 > others is stable in and out of sample), but the
*level* of the deployed Sharpe is not distinguishable from selection noise once
the true search breadth is acknowledged. Cost sensitivity is mild at daily
horizons. MinTRL is 22 months (SWING) / 13 months (POSITIONAL) of live trading
before the Sharpe means anything.

---

## What Phase 3 builds, in order

1. **Exits first** (was Phase 4): +1 R partial, breakeven, chandelier trail;
   desired-state heartbeat. Re-run this harness. Expect the largest single
   expectancy gain of the project.
2. **S1 rewrite**: trigger ∧ trend ≥ 18, no gate, no threshold.
3. **S2 removal.**
4. **Regime → metadata**; `useRegimeFilter` default OFF.
5. **S3 → trigger + metadata**; selection moves to the server's cross-sectional rank.
6. **S4 unchanged** at threshold 75; consider dropping `vol`/`htf` from its rubric.
7. **Parity gate**: export the Strategy Tester trade list for SPY and one single
   name, run `parity_test.py`, and only then treat these numbers as describing
   the system that trades.

What not to do: do not turn on `useScoreConfidence`. The only strategy where
score predicts outcome is S4, and even there the top decile is not the best
decile. Sizing on this score would allocate the most capital to S3's highest
scores, which are its *worst* decile.
