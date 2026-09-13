# Phase 4 — Cross-profile allocation, in the terms the account experiences

Phases 2–3 measured everything in R per trade and per symbol. That hid the
constraint that actually binds: the executor's heat cap (10% NAV, 3% per
position) is 3–10 slots, and SWING and POSITIONAL compete for them. Phase 4
simulates both profiles' v3 candidates from the same 48 symbols through a
shared slot budget, sizes each admitted trade as a fixed fraction of current
equity, and reports CAGR, volatility, Sharpe and drawdown in % NAV.

Same caveats as before, plus one: P&L is booked at exit, so `DD (closed)`
ignores open losses and `DD bound` assumes every open position is stopped at
the trough — the truth lies between. **Use these tables for the ranking of
rules and the shape of the trade-offs, not for return expectations.** The
universe is today's survivors.

Reports: `research/out/phase4_portfolio.md`. Admission logic:
`server/allocator.py`, imported by the simulation.

---

## 1. Four rules, one that matters

| cap 10 · 1% risk · test 2021+ | CAGR | vol | Sharpe | DD closed | DD bound | worst month | trades/yr |
|---|---:|---:|---:|---:|---:|---:|---:|
| FIFO, **one position per symbol** | +20.2% | 14.2% | **1.32** | −17.6% | −26.2% | −8.1% | 109 |
| per-bar-expectancy tiebreak, one per symbol | +20.0% | 14.6% | 1.28 | −17.7% | −18.8% | −10.6% | 112 |
| priority by per-trade expectancy, one per symbol | +17.2% | 12.6% | 1.28 | −15.3% | −23.6% | −11.9% | 78 |
| reserve half the slots per profile, one per symbol | +13.3% | 11.4% | 1.11 | −12.9% | −18.0% | −7.9% | 78 |
| FIFO, symbol may be held by both profiles | +10.6% | 13.0% | 0.81 | −15.8% | −16.8% | −12.0% | 92 |

- **One open position per symbol across profiles is the rule that matters.**
  Allowing SWING and POSITIONAL to hold the same name at once takes Sharpe
  from 1.32 to 0.81 — it is the same directional bet twice, and it crowds
  out an uncorrelated one.
- **Arrival order is as good as any ranking.** FIFO and the per-bar tiebreak
  are indistinguishable; the tiebreak only decides same-bar collisions. The
  allocator ships with `per_bar` because it is deterministic and has a
  rationale (S1 0.06 R/bar > S4-SWING 0.012 ≈ S3 0.012 > S4-POSITIONAL
  0.006), not because it measurably beats first-come.
- **Priority by per-trade expectancy is the wrong rule under a shared cap.**
  It admits POSITIONAL S4 first — the highest expectancy per trade — and those
  positions then hold a slot for 54 bars at half the per-bar rate of a SWING
  trade. Returns drop by a sixth.
- **Reserving slots per profile minimises drawdown and costs a third of the
  return.** A legitimate choice for a drawdown-first mandate; not the default.

## 2. POSITIONAL earns its keep only with its own capital

| cap 10 · 1% risk · test 2021+ | CAGR | vol | Sharpe | DD closed | trades/yr |
|---|---:|---:|---:|---:|---:|
| SWING only | +20.9% | 14.9% | 1.31 | −17.7% | 113 |
| POSITIONAL only | +9.9% | 7.0% | **1.33** | **−10.7%** | 36 |
| both, shared cap, FIFO | +20.2% | 14.2% | 1.32 | −17.6% | 109 |

Adding POSITIONAL to a shared cap-10 book adds nothing — it takes 12–20 of
~110 slots a year and the combined result equals SWING alone. On its own
capital it is a different product: half the return at half the volatility,
the same Sharpe, a drawdown two-fifths smaller. Run it in a separate sleeve
(the low-turnover retirement money is the obvious candidate — 0.75 trades per
symbol-year, 55-bar holds, 62% hit rate, manual execution is feasible) or do
not run it. Do not let it share the active account's heat.

## 3. Slot budget and risk per trade

The executor's heat cap fixes the product `slots × risk%`. At 10% heat:

| slots × risk | test 2021+ Sharpe | DD closed / bound | all-period DD closed / bound |
|---|---:|---:|---:|
| 5 × 2% *(not run — see below)* | | | |
| **10 × 1%** | **1.32** | −17.6% / −26.2% | −24.3% / −27.5% |
| 10 × 1.5% (15% heat) | 1.28 | −25.4% / — | −35.0% / −40.0% |
| 8 × 1% (8% heat) | 1.06 | −14.1% / −20.3% | |
| 5 × 1% (5% heat) | 0.32 | −16.1% / −17.1% | |

Two things:

- **Ten slots at 1% is the configuration.** Eight loses a quarter of the
  Sharpe to lost diversification; five collapses — with the heat cap binding
  in every drawdown, a 5-slot book spends most of the test period unable to
  admit, and the return goes to +2.7%. Fifteen slots looks better (1.66) but
  needs 15% heat, above the executor's cap.
- **1.5% per trade buys a third more return for a third more drawdown** and
  a lower Sharpe. The all-period bound at 1.5% is −40%. At 1% it is −27.5%.
  Take 1%; the extra return is not worth −40%.

The 5 × 2% row is left blank deliberately: fewer, larger positions
concentrate exactly the idiosyncratic risk the 48-name universe was meant to
diversify, and nothing in Phases 2–3 supports it.

## 4. What ships

`server/` — drop-in modules for the Windows webhook server, with tests
(`python -m pytest server/tests`, 21 passing):

- `schema.py` — pydantic models for payload 2.1.0. Superset of the v1
  `TVSignal`; every new field optional; `extra="ignore"`. Rejects
  `schema_version` below the floor (un-recreated alerts), `warmup_ok=false`,
  and `MANAGE` without a lifecycle event. `idempotency_key` property.
- `allocator.py` — `Allocator.admit_batch(candidates, open_positions, equity)`
  → decisions with reasons. Symbol uniqueness, slot cap, heat cap, four
  tiebreak rules. **This is the module `research/portfolio_sim.py` imports**,
  so the rule validated above and the rule the server runs cannot drift;
  `tests/test_allocator_replay.py` asserts they reproduce the same numbers.
- `reconciler.py` — `reconcile(signal, broker_position, broker_orders,
  entry_qty, full_qty)` → minimal order diff. ENTRY places entry + stop +
  partial limit; SCALE/MODIFY replace the stop and reconcile size (sells the
  difference if the partial was missed); EXIT cancels and flattens;
  HEARTBEAT repairs drift and never chases a position the broker does not
  hold. Idempotent: the same desired state twice yields no orders.

`SERVER_PATCH.md` items 9–10 wire them in.

## 5. What this does not settle

- **The parity gate is still unrun** — three phases of results rest on a
  Python mirror that is faithful by construction, and the exit engine is a new
  surface. One Strategy Tester export.
- **Mark-to-market.** The simulation books P&L at exit. True daily volatility
  and drawdown are higher than `closed` and lower than `bound`. A daily-marked
  equity curve needs per-day position marks the trade lists do not carry;
  cheap to add, not done.
- **Survivorship.** Levels are optimistic. The 2021+ window is 5.7 years with
  one bear market. MinTRL from Phase 3 (21–26 months live) still applies.
- **Correlation.** Symbol uniqueness prevents the same name twice; it does not
  prevent ten semiconductor longs. The server's `SECTOR_MAP` and the existing
  "max 3 per sector" rule should sit in front of the allocator, not behind it.
