# MNQ MTF Swing Long

A Pine v6 long-only swing engine for MNQ on a 15-minute chart, with a strict
4H → 1H → 15M hierarchy and TradingView alerts shaped for the SignalStack
webhook. Nothing arms unless the 4H regime allows longs, nothing triggers
unless the 1H is pulling back into real support, and nothing enters until the
15M sequence completes.

```
mnq_mtf_swing.pine        the indicator — put this on the chart
mnq_mtf_swing_bt.pine     strategy twin for the Strategy Tester (GENERATED)
research/engine.py        the rules in executable Python; the Pine is a port of it
research/bars.py          15M -> 1H/4H aggregation anchored to the session open
research/ta.py            EMA / ATR / pivot primitives with Pine's seeding rules
research/build_twin.py    regenerates the twin by text transform
research/pine_lint.py     static checks the Pine compiler is not here to run
research/tests/           29 tests: gate arithmetic, exits, calendar, causality
research/data/            MNQ 15m/1h/4h sample bars used by the tests
```

**Status: not validated.** The rules are implemented and internally checked, and
the Pine has not been through the TradingView compiler because this environment
has no TradingView session. On the only sample available (2.5 months of 15M
bars) the rule set produced 5 trades. That is a plausibility check, not
evidence. Read *What still has to be proven* before risking money.

---

## The rules

Everything is evaluated once per **closed** 15M bar. The one intrabar exception
is the stop/target touch watch, which is what lets an exit alert fire when the
level trades instead of up to 15 minutes later.

### 4H — market regime

| Rule | The phrase it implements |
|---|---|
| `PH4[0] > PH4[1]` and `PL4[0] > PL4[1]` | higher highs **and** higher lows on the last two confirmed 4H pivots |
| close above the slow EMA, fast EMA above slow, slow EMA above its value 3 closed bars ago | rising structure |
| close above the most recent confirmed 4H higher low | price above major support |
| the target scan vetoes the trade when the nearest strong level is closer than Min R:R | no immediate strong resistance |

The fourth rule is deliberately **not** a separate gate. "No immediate strong
resistance" only matters if it stops you taking a trade, so it is enforced where
it has that consequence: at the entry bar, when the target is chosen. A 4H pivot
high, the provisional 4H high, or the 24-hour high sitting inside Min R:R skips
the trade outright (`TP_STRONG_WALL`). Making it a separate gate as well would
have meant a second tolerance parameter measuring the same thing.

### 1H — setup

Fast EMA above slow EMA and the slow EMA rising. A real pullback: the 24-hour
high minus the 1H close is at least half a 1H ATR. And price testing one of four
support kinds, whichever is **lowest** (the lowest level gives the most
conservative invalidation):

| Kind | Level |
|---|---|
| `PL` | the most recent 1H pivot low, if it is higher than the one before it — rising support |
| `BRK` | the most recent 1H pivot high price has since closed above, still below the current close, not more than two tolerances under the slow EMA — a prior breakout, retested |
| `EMA20` | the fast EMA |
| `EMA50` | the slow EMA |

A level is "tested" when the 15M bar's low reaches within one tolerance of it and
the close holds at or above it. The test is on the 15M bar against the 1H level,
so a rejection that happens inside a still-forming 1H bar is not missed.

Volume contraction (1H volume SMA5 below SMA20) is reported on the dashboard but
does **not** block by default, because the user asked for it as *preferred*.
Switching it on is also a parity hazard: TradingView and your broker's feed
report different futures volume.

### 15M — trigger

```
IDLE ──test a zone──▶ AT_ZONE ──rejection candle──▶ REJECTED
                         ▲                              │
                         └──deeper low, no rejection────┤ confirmed higher low
                                                        ▼
                    IN_TRADE ◀──close above the swing high── HL_OK
```

* **Rejection candle**: the low reaches into the zone, the close is back above
  the zone level, and the close is in the upper half of the bar's range.
* **Higher low**: a confirmed 15M pivot low above the rejection low and at or
  above the zone floor. Confirmation costs `pivLTF` bars (30 minutes at the
  default) — that lag is the price of a trigger that does not repaint.
* **Break**: a close above the highest high between the rejection low and the
  higher low. Entry is at that close.
* A deeper low that still rejects re-rejects **in place** rather than killing the
  setup: a second, deeper test of the same level is the canonical version of
  this pattern, not a failure.
* The setup dies on: 4H regime lost, 1H trend lost, a close below the zone
  floor, a weekend gap, price leaving the zone upward without rejecting, or a
  stage timeout.

### Stop and target

**Stop** is 1 tick below the 15M higher low, as asked. The 1H setup invalidation
(the zone floor) is only the fallback, used when the higher-low stop is tighter
than the noise floor of `max(0.5 × ATR15, 4 ticks)`. An earlier draft had it the
other way round — substituting the zone floor whenever the higher low sat inside
the zone band — which fired on almost every setup, made every stop zone-width,
and let the risk cap kill 5 of 9 breaks. The stop source is reported on the
entry label and the dashboard so you can see which rule paid.

**Target** walks the merged candidate levels upward and takes the first that pays
at least Min R:R, 2 ticks below the level:

* **Strong** levels (4H pivot highs, the provisional 4H high, the 24-hour high)
  inside Min R:R **skip the trade**.
* **Weak** levels (1H pivot highs) inside Min R:R are ignored and the scan
  continues.
* No qualifying level at all → the 1:2 fallback.

All prices are rounded to the tick **before** any risk/reward comparison, so the
gate tests the price that would actually be worked at the broker.

---

## Parameters

Eleven inputs. Four are genuinely tuned; the rest are structural, meaning they
name a thing the user specified rather than a number fitted to data.

| Input | Default | Kind | Note |
|---|---|---|---|
| Fast EMA length | 20 | structural | the user's 20, on both 4H and 1H |
| Slow EMA length | 50 | structural | the user's 50 |
| 4H / 1H pivot strength | 3 | structural | a pivot is confirmed 3 bars after the extreme, so the newest 4H structure is up to 12 hours old |
| 15M pivot strength | 2 | structural | higher low confirmed 30 minutes after it forms |
| Zone half-width (× ATR 1H) | 0.5 | **tuned** | the one parameter everything else leans on; sweep 0.25 / 0.5 / 0.75 |
| Stage timeout (bars) | 16 | **tuned** | counted in bars, so halts and weekends do not consume it |
| Min R:R | 1.5 | **tuned** | also the strong-resistance veto threshold |
| Fallback R:R | 2.0 | structural | the user's 1:2 |
| Max risk (× ATR 1H) | 2.0 | **tuned** | 0 disables; a wider stop is not a swing stop for this setup |
| Require volume contraction | off | structural | preferred, not required |
| Block entries N days before expiry | 3 | structural | 0 disables |

Constants deliberately kept out of the input list, so the tuned surface stays
small: the 0.5 × ATR pullback minimum, the `max(0.5 × ATR15, 4 ticks)` risk
floor, the 0.25 × ATR merge distance for target levels, the 2-tick target and
1-tick stop offsets, the 8-deep pivot rings, the 24-bar lookback for the pullback
high, and the 5/20 volume averages. Each is a design choice; a sweep of ±1 step
on any of them must be flat or the rule it serves should be removed, not tuned.

---

## Non-repainting

Both higher timeframes are read with the idiom the Pine manual documents for
this and that `adaptive_scanner/asr_engine.pine` uses as `[F5]`:

```pinescript
[c4, ef4, es4, ...] = request.security(syminfo.tickerid, "240",
     f_ctx4(emaFast, emaSlow, pivHTF), lookahead = barmerge.lookahead_on)
```

with **every element of the returned tuple at offset `[1]`** inside the function.
The `[1]` and `lookahead_on` are interdependent: together they give the last
**closed** higher-timeframe bar, and that value is the same on historical and
realtime bars. The 4H bar that closes at the same instant as the current 15M bar
is deliberately invisible until the next 15M bar.

Two further choices protect this:

* **Pivot rings live in the chart context**, not inside the `request.security`
  function. A forming 4H bar re-executes that function on every tick, so a ring
  mutated inside it could accept a pivot that the completed bar would reject.
  The function returns scalars; the chart-side code pushes them once per new
  higher-timeframe bar.
* **All state changes happen under `barstate.isconfirmed`**, so a signal never
  appears and disappears inside a forming bar.

The one thing that is intentionally intrabar is the stop/target watch. It is
computed from the values committed on the *previous* bar and placed **above** the
state machine in the source, so the state machine resetting on the same tick
cannot swallow the alert.

---

## Deployment: TradingView → SignalStack → broker

1. Open `CME_MINI:MNQ1!` (or the front month) on the **15 minute** chart, paste
   `mnq_mtf_swing.pine` into the Pine editor, compile, add to chart.
2. Set **Webhook symbol** to what *your* broker expects. This is not the chart
   symbol and the continuous `MNQ1!` is not a documented SignalStack symbol:

   | Broker | Symbol format | Example (Dec 2025) |
   |---|---|---|
   | Tradovate (also NinjaTrader) | root + month + 1-digit year | `MNQZ5` |
   | Interactive Brokers | root + month + 2-digit year | `MNQZ25` |
   | TradeStation | root only | `MNQ` |
   | TastyTrade | `/` + root + month + 1-digit year | `/MNQZ5` |
   | Optimus | exchange:root.month+year | `XCME:MNQ.Z25` |

3. Create **one** alert: condition = this script, **"Any alert() function call"**.
   Leave the message box **empty** — `alert()` supplies the JSON. Paste your
   SignalStack webhook URL. The URL is the credential; no header is needed.
4. Set **Exit action** for your broker and test it on a **Test webhook** first.

### What the payloads look like

SignalStack's payload is flat JSON with snake_case keys, and `"class":"future"`
is required for futures. Order type is inferred from which price keys are
present; with none, these are market orders.

```json
{"symbol":"MNQZ5","action":"buy","quantity":1,"class":"future"}
{"symbol":"MNQZ5","action":"close","quantity":1,"class":"future"}
```

### The bracket problem — read this before going live

**SignalStack's payload schema has no bracket, OCO, stop-loss or take-profit
field.** `limit_price` and `stop_price` describe the *entry* order type, not an
attached exit. So the stop and target cannot travel with the entry: the **SL and
TP alerts from this script are the exits**. Three consequences:

* If TradingView misses a bar, your alert expires, or the webhook fails, the
  position has **no protective order at the broker**. Set a broker-side maximum
  position and check the position matches the chart.
* The exit action is broker-dependent. `close` is documented for Interactive
  Brokers, TradeStation, TastyTrade and E-Trade, and flattens whatever is open
  regardless of side. **Tradovate documents only `buy` and `sell`** — there, a
  `sell` sent while you are already flat **opens a short**. That is why the exit
  action is an input and why the default is `close`.
* Alerts fire only on realtime bars, and TradingView cancels a webhook request
  that takes more than 3 seconds.

Housekeeping: webhooks need a paid TradingView plan with two-factor
authentication enabled. TradingView snapshots the script when the alert is
created, so **every edit to this file means re-creating the alert**. On plans
below Premium, alerts expire after two months and must be re-armed.

---

## What still has to be proven

This is the part that decides whether the system is worth trading, and none of
it has been done.

**The adverse prior is in this repository.** `adaptive_scanner/PHASE5_FINDINGS.md`
found no after-cost edge in 15M intraday long constructions across 48 names and
193 sessions, and no edge over a random-entry control. `PHASE6_FINDINGS.md` then
measured 15M entry confirmations (opening-range break, VWAP reclaim) at **−0.16
to −0.17 R per trade against a plain fill** on identical daily swing signals,
with intervals excluding zero. This product differs — MNQ rather than equities,
held overnight rather than flat by the close, gated by 4H and 1H structure
rather than intraday alone — but the burden is on it to show the difference
matters.

**The null it must beat.** Not "is it profitable". The comparison is paired, on
identical setups: take the same 4H regime and 1H zone, and instead of waiting
for rejection → higher low → break, enter at the close of the first 15M bar back
above the 1H fast EMA with the same stop-and-target rules. Count a setup the full
trigger never entered as 0 R for that arm. If the full trigger does not beat that
by a margin whose bootstrap interval excludes zero, ship the simpler rule.

**Sample size.** At roughly one to three setups a week, detecting a +0.15 R
effect at 80% power needs on the order of 400 trades — three to eight years of
15M NQ history. TradingView's ~5,000-bar 15M window cannot host that test; it is
a fixture, not a sample. Below 300 pairs the honest answer is "inconclusive".

**Also required before live money:**

* Sweep the four tuned parameters and confirm a flat plateau. Monotone
  dependence on the zone half-width means the rule is fitting noise.
* Ablate each component separately: no 4H gate, no zone, no higher-low
  requirement, fixed 2R target, pure higher-low stop.
* Walk forward, then deflated Sharpe at the honest trial count and PBO — the
  standard `adaptive_scanner/research/analysis.py` already applies.
* Costs: about $1.50 round-trip commission plus a tick or two of slippage per
  side. On a 20-40 point stop that is 0.04-0.08 R, small but not zero.

### Verification checklist

Run these against the chart before trusting a signal.

1. **Compile.** Pine editor, no errors. Nothing here has been through the real
   compiler.
2. **No repaint.** Note the dashboard state on a forming bar, then again after it
   closes. Nothing may change retroactively.
3. **Higher-timeframe alignment.** Plot `request.security(syminfo.tickerid,
   "240", time[1])` and confirm the 4H bars open at 18:00, 22:00, 02:00, 06:00,
   10:00 and 14:00 ET. A one-hour anchor error changes every 4H pivot.
4. **Payload shape.** Fire once against a SignalStack **Test** webhook and
   confirm the JSON is exactly the documented keys.
5. **Exit semantics.** On a paper account, open a position, send the exit alert,
   and confirm it flattens rather than reversing.
6. **Twin parity.** `python research/build_twin.py --check` must pass, so the
   backtested file is the same rules as the charted one.

---

## Research harness

```bash
cd mnq_mtf_swing/research
pip install numpy pytest
python -m pytest tests -q          # 29 tests
python engine.py                   # run the rules over the committed sample
python build_twin.py --check       # the twin is not stale
python pine_lint.py ../*.pine      # static checks on both scripts
```

`engine.py` is the rule set in executable form and the Pine is a port of it. If
the two ever disagree, the mirror and its tests decide. The tests cover the entry
gate arithmetic, stop-wins and gap fills, the calendar helpers, and a
prefix-truncation check that no rule reads a bar that had not closed —
truncating the data must not change any earlier decision.

Two deliberate divergences are worth knowing:

* **Stop wins** when one bar touches both the stop and the target. This is
  conservative and it differs from `adaptive_scanner/research/labels.py`, which
  resolves the same bar with an open-to-nearer-extreme path heuristic. Live fills
  should therefore be slightly better than the mirror, not worse — do not tune to
  the mirror's pessimism.
* **The strategy twin is optimistic** on exactly those bars, because
  TradingView's broker emulator uses its own path assumption. Count how many
  trades exit on a bar spanning both levels before trusting its headline number.

## Licence

This directory is MPL-2.0 (`© mukeshyadavus`), as with `adaptive_scanner/`; the
repository root is GPL-3.0. See `adaptive_scanner/LICENSE-NOTE.md`.
