# Phase 3 — Exits, rules, and the deployed v3 configuration

Same harness, universe and caveats as Phase 2 (48 survivor-universe US
equities/ETFs, daily, 2014–2026; R net of 3 bps per leg; parity gate still
pending a Strategy Tester export). Every selection below was made on entries
before 2021-01-01 and confirmed on 2021 onward. Reports:
`research/out/exit_study_*.md`, `phase3_simulation.md`, `phase3_slot_cap.md`,
`phase3_variants.md`, `phase3_final.md`.

---

## 1. Exits — the plan's proposal lost; a different exit won

Fourteen exit models were applied to every long trigger event and to the
Phase 2 deployed set. The Phase 2 plan proposed *partial at +1 R, breakeven,
chandelier trail, time stop* (M2). It **underperformed the fixed-target exit on
every population** (SWING deployed, test: +0.082 vs +0.089). Two things won,
and they are different for different strategies:

| strategy | selected exit | why |
|---|---|---|
| **S1** | chandelier 3×ATR from entry, no partial, profile time stop kept (M5) | +0.62 R test vs +0.56 current; best R-per-bar in the study. Partials cut its bounce winners (~+0.35); long trails with no time stop collapse OOS (+0.21). |
| **S3, S4** | 50% off at +1 R, stop to breakeven, chandelier 3×ATR on the remainder, **no time stop** (M8) | Highest train Sharpe for both strategies in both profiles, confirmed best or top-2 on test. S3: +0.11 → +0.17/+0.21; S4 POSITIONAL: +0.32 → +0.34 at equal Sharpe. |

The lever is **removing the time stop** — but only with a trail in its place.
M0's fixed target was the right exit for nothing. Trail width: 3×ATR; 2×ATR
exits too early everywhere, 4×ATR wins in-sample and collapses out of sample
for S1.

---

## 2. Rules — and the constraint the per-trade numbers hid

Applying the Phase 2 decisions (S1 on trigger ∧ trend ≥ 18, S2 removed, S3 on
trigger, regime gate off, priority S1 > S4 > S3, one position per chart) and
simulating sequentially per symbol:

| | v2 (Phase 2) | v3 rules + v3 exits |
|---|---:|---:|
| SWING, annualized monthly Sharpe, test | 0.69 | **1.29** |
| SWING, R per trade, test | +0.088 | **+0.207** |
| SWING, mean open positions / peak | 4.4 / 21 | **24 / 47** |

The last row is the problem. S3 on trigger makes the system nearly always
fully invested across 48 names. The executor caps heat at 10% NAV and 3% per
position — that is 3 to 10 slots, not 47 — so **which candidates get the slots
is the binding decision**, and the cross-sectional feature check says nothing
predicts S3 outcomes well enough to rank on (best: 60-day ROC at ρ = −0.085).

Re-running with a slot cap and priority admission (S1 > S4 > S3):

| cap 10, test 2021+ | trades | mean R | Sharpe | R / year | max DD (R) |
|---|---:|---:|---:|---:|---:|
| SWING v2 | 667 | +0.086 | 0.69 | +10.1 | −22.5 |
| SWING v3, S3 unthrottled | 686 | +0.131 | 0.83 | +15.8 | −25.5 |
| **SWING v3, S3 gated ≥ 70** | 603 | +0.172 | **1.03** | +18.3 | −24.4 |
| POSITIONAL v2 | 416 | +0.183 | 1.10 | +13.5 | −21.5 |
| POSITIONAL v3, all three | 322 | +0.106 | 0.55 | +6.1 | −29.8 |
| **POSITIONAL v3, S4 only** | 194 | +0.263 | **1.27** | +9.0 | **−10.9** |

Two findings:

- **The S3 score threshold is worthless as a predictor and valuable as a rate
  limiter.** It throttles the S3 stream so S4's longer, better trades get
  slots. Under a cap of 10 or more, gating S3 at 70 raises SWING Sharpe from
  0.83 to 1.03. (At cap 5 the ungated variant did better — 0.81 vs 0.62 — on
  ~350 trades; noise-level, but noted.)
- **POSITIONAL is an S4-only system.** Every S3 variant dilutes it; S1 loses
  outright with wide stops (+0.10 R, 32% hit). S4-only halves capacity versus
  v2 (+9 vs +13.5 R/yr) and pays for it with the best Sharpe and the smallest
  drawdown of any configuration tested.

---

## 3. Deployed v3 — what `asr_engine.pine` now does by default

| | SWING | POSITIONAL |
|---|---|---|
| S1 | on: trigger ∧ trend ≥ 18; chandelier 3×ATR from entry; 15-day time stop | **off** |
| S3 | on: trigger ∧ score ≥ 70 (rate limiter); 50% at +1 R, BE, chandelier 3×ATR, no time stop | **off** (toggle available) |
| S4 | on: score ≥ 75; same exit as S3 | on: score ≥ 75; same exit |
| S2 | removed | removed |
| Regime | metadata only | metadata only |
| Selection | highest-priority eligible: S1 > S4 > S3 | S4 |
| Positions | one per chart | one per chart |

**Headline, cap 10, test 2021+ (from `phase3_final.md`):**

| | trades | mean R | hit | PF | Sharpe | R / year | worst month | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SWING v2 | 667 | +0.086 | 51% | 1.20 | 0.69 | +10.1 | −6.2 | −22.5 |
| **SWING v3** | 619 | **+0.216** | 54% | 1.45 | **1.21** | **+23.6** | −9.3 | −19.1 |
| POSITIONAL v2 | 416 | +0.183 | 52% | 1.46 | 1.10 | +13.5 | −7.0 | −21.5 |
| **POSITIONAL v3** | 194 | **+0.263** | 62% | 1.71 | **1.27** | +9.0 | −5.0 | **−10.9** |

Uncapped test: SWING 1.36 vs 0.69; POSITIONAL 1.46 vs 1.12 with max DD −8.7 vs
−41.6.

**Deflated Sharpe at cap 10** (monthly units; the Phase 3 search was ~14 exit
models × 7 rule variants, so N = 100 is the enumerated figure and N = 500 the
honest one): SWING 0.57 / 0.28; POSITIONAL 0.80 / 0.57. POSITIONAL S4-only is
the more robust of the two — fewer moving parts, fewer trials behind it.
MinTRL: 26 and 21 months of live trading before the Sharpe means anything.

---

## 4. What changed in the Pine (v3.0.0)

- **Exit engine.** The indicator now carries one piece of state: the position
  it last entered, managed bar by bar with the labeller's fill rules (gap at
  open; open→high→low vs open→low→high when both levels are inside the bar;
  time stop at close; stop changes effective next bar). It emits
  `ENTRY / SCALE / MODIFY / EXIT / HEARTBEAT` events and a live
  `desired_state` (working stop, partial level, trail level, size open).
- **Payload.** One `alert()` per bar. `action` is `BUY` on ENTRY and `MANAGE`
  on lifecycle events — the unpatched `TVSignal` model rejects `MANAGE`
  outright, which is the safe failure (a `SELL` would have opened a short).
  `emitLifecycle` defaults ON; turn it OFF until `SERVER_PATCH.md` item 9 is
  applied. Schema 2.1.0.
- **Rules.** S2 deleted. S1 gated by its own trend component, SWING-only. S3
  gated at 70 as a rate limiter, off in POSITIONAL. S4 unchanged at 75.
  `useRegimeFilter` defaults OFF. Winner by priority, not max score.
- **Twin.** Regenerated; its execution block places a partial-leg exit and a
  remainder exit re-issued every bar from the engine's working stop, plus the
  S1 time stop and a resync guard.

---

## 5. Still not done

- **Parity gate.** Unrun. Export the Strategy Tester trade list for SPY on 1D
  under each profile and run `research/parity_test.py`. The v3 exit engine is
  a new surface for divergence; the parity test is where it would show.
- **Cross-profile capacity.** SWING and POSITIONAL share the account's heat
  cap. The slot simulations were per profile. A portfolio allocator that
  admits across both by priority is a Phase 4 item, and the server is where
  it lives.
- **Survivorship.** Unchanged. Absolute levels are optimistic; the v2→v3
  comparisons are not materially affected.
- `useScoreConfidence` stays OFF. Nothing in Phase 3 changed the Phase 2
  finding that score is not a sizing signal.
