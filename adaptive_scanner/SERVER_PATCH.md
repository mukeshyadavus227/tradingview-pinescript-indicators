# Server-side changes required

The Python pipeline (`server.py`, `engine.py`, `config.py`) lives on the Windows
host and is not in this repository, so this is a specification rather than a
diff. Items 1 and 2 are the ones that fix production; the rest are Phase 0
infrastructure for schema v2.

Referenced against the pipeline spec in the `tv-webhook-connector` skill.

---

## 1. Accept and act on the stop — highest priority

`TVSignal` already declares `stop: float = 0.0`. The engine now writes the
rounded stop price there, so **no model change is needed for this one** — but
the executor must actually place a bracket with it instead of a bare MKT order.

Verify with:

```
curl -X POST "https://<host>/webhook?token=$TV_WEBHOOK_TOKEN" \
     -H 'Content-Type: application/json' -d @sample_signal.json
cat signals/<newest>.json | python -m json.tool | grep -E '"stop"|"comment"'
```

If `stop` persists as `0.0`, the payload is not reaching the model — check
whether the model is rejecting unknown keys rather than ignoring them.

## 2. Read `confidence`

The sizing table keys off `confidence` and treats "not set" as 1.5% NAV. Add:

```python
confidence: float = Field(default=0.6, ge=0.0, le=1.0)
```

The engine emits `0.6` by default, which reproduces current behaviour exactly.
It emits a score-derived value only when the operator turns on
`useScoreConfidence`, which should stay off until Phase 2 validates the score.

## 3. Extend the model for schema v2

Add as optional nested models (all default `None`, so old alerts still validate):

```python
schema_version: str = "1.0.0"
signal_id:      str | None = None
profile:        str | None = None          # SWING | POSITIONAL | ...
account_route:  str | None = None          # IBKR_TAXABLE | IBKR_IRA | FIDELITY_403B_MANUAL
manual_only:    bool = False
thesis:         Thesis       | None = None
desired_state:  DesiredState | None = None
sizing:         Sizing       | None = None
scores:         Scores       | None = None
regime:         Regime       | None = None
context:        Context      | None = None
meta:           Meta         | None = None
```

Keep `extra='ignore'` on the model config so a newer script against an older
server degrades rather than failing.

## 4. Reject on `meta.warmup_ok` and `schema_version`

```python
if sig.meta and sig.meta.warmup_ok is False:
    reject("warmup")                       # regime/percentiles not yet valid
if version_tuple(sig.schema_version) < SCHEMA_FLOOR:
    reject("stale_alert")                  # TradingView alert predates an engine edit
```

The second one matters more than it looks. TradingView snapshots the script when
an alert is created, so an un-recreated alert keeps trading old logic forever and
gives no outward sign. A version floor turns that into a visible rejection.

## 5. Idempotency

`signal_id` is `<symbol>|<profile>|<bar_time>|<seq>` and is deterministic. Hash
it server-side and refuse a duplicate:

```python
key = hashlib.sha1(sig.signal_id.encode()).hexdigest()
if key in seen_keys:      # TTL ~24h
    return {"status": "duplicate", "signal_id": sig.signal_id}
```

## 6. Make staleness and order caps per-profile

Current config is global: signal staleness 5 minutes, `max_orders_per_day` 20.

- **Staleness.** Five minutes is right for intraday and wrong for a daily close:
  a 1D signal fires at 16:00 ET and is dead before anything can act on it.
  With the Phase 6 fill rule (item 11) a SWING / POSITIONAL signal is valid
  until 30 minutes after the next session's open, not for a fixed number of
  minutes. Suggested: `INTRADAY 5min / SWING, POSITIONAL next open + 30min /
  LONGTERM 48h`.
- **Order cap.** Twenty per day across the whole watchlist is fine for swing and
  will saturate in the first hour of an intraday profile across 20 names. Make
  it per-profile, and add a per-symbol-per-day cap.

## 7. `manual_only` queue

For `account_route == "FIDELITY_403B_MANUAL"`: never route to IBKR. Render an
order ticket and notify. The retirement sleeve has no broker API, cash settles
T+1 (good-faith-violation risk), and it must be structurally impossible for a
signal on that route to reach an order endpoint.

## 8. Rotate the webhook token

The token is stored in plaintext in the cloud-synced `tv-webhook-connector`
SKILL.md. Rotate it, move it to an environment variable, and replace the literal
in the skill with a placeholder. Do not paste the current or new value into any
file in this repository.

## 9. Lifecycle events and desired-state reconciliation (Phase 3)

**Reference implementation: `server/schema.py` and `server/reconciler.py`**
(`python -m pytest server/tests`). Replace `TVSignal` with `SignalV2` — it is
a superset with the same v1 field names and defaults — and call
`reconcile(signal, broker_position, broker_orders, entry_qty, full_qty)` on
every lifecycle payload; it returns the minimal order diff and is idempotent.

Schema 2.1.0 payloads carry `event`, `events[]` and a live `desired_state`.
`action` is `BUY` on ENTRY and **`MANAGE`** on every other event.

```python
action: Literal["BUY", "SELL", "MANAGE"]
event:  Literal["ENTRY", "SCALE", "MODIFY", "EXIT", "HEARTBEAT"] | None = None
events: list[Event] | None = None
desired_state: DesiredState | None = None   # side, entry_ref, risk, stop, size_pct_open,
                                            # partial_at, partial_pct, trail{k, active, level},
                                            # time_stop_at, bars_in_trade
```

Route by `event`, never by `action`:

| event | server action |
|---|---|
| ENTRY | place entry + initial stop; for S3/S4 also a limit for `partial_pct` at `partial_at` |
| SCALE | confirm the partial filled (or fill it at market if the limit was missed); move stop to `desired_state.stop` |
| MODIFY | replace the working stop with `desired_state.stop` |
| EXIT | flatten at market; reason in `events[].reason` |
| HEARTBEAT | reconcile: if broker position ≠ `desired_state` (side, size_pct_open, stop within 1 tick), correct it |

Reconciliation is idempotent and level-triggered, so a missed MODIFY is
repaired by the next HEARTBEAT. Dedupe on `signal_id` (now
`symbol|profile|bar_time|event|seq`).

**Slot admission.** Under the portfolio heat cap, admit same-bar candidates
by strategy priority S1 > S4 > S3 (the order of validated expectancy). Do not
rank S3 candidates on score — it does not predict their outcome.

**Until this item lands**, tell the operator to set the indicator's *Emit
SCALE / MODIFY / EXIT events* input OFF; ENTRY payloads still carry the
initial stop and the partial level in `comment`.

## 10. Slot allocation across profiles (Phase 4)

**Reference implementation: `server/allocator.py`.** Before sizing an ENTRY,
call `Allocator(AllocatorConfig(max_positions=10, risk_pct=1.0,
max_heat_pct=10.0, one_per_symbol=True, rule="per_bar")).admit_batch(...)`
with every ENTRY received on the same bar and the current open positions.
Rejections carry a reason (`symbol already held`, `slots full`, `heat cap`).

Validated choices (PHASE4_FINDINGS.md): one position per symbol across
profiles is non-negotiable; ten slots at 1% risk; keep the existing "max 3 per
sector" rule in front of the allocator. Do not run POSITIONAL against the
same heat budget as SWING — give it its own sleeve or leave it off.

## 11. Entry fill rule (Phase 6)

The engine signals at the daily close. Fill **market-on-open the next
session** and place the bracket at the engine's absolute `stop` (do not
re-anchor the stop distance to the fill). Over twelve years this costs
−0.02 R per trade against the harness's close-fill assumption; the numbers
in the README are already the next-open numbers.

Do not add a limit-at-signal-close, a limit-with-MOC-fallback, or an
opening-range / VWAP confirmation before the fill. Each was tested on
identical signals (`PHASE6_FINDINGS.md`); none beats the open per signal and
the two intraday confirmations lose by 0.16–0.17 R per trade.

Log `fill_px`, `signal_px` (`desired_state.entry_ref`) and `atr_d` on every
entry so `(fill − signal) / atr_d` can be monitored: the 2025-12 → 2026-09
window ran a median +0.08 ATR overnight slip and a −0.14 R per-trade haircut,
seven times the twelve-year average. Two consecutive quarters above +0.10 ATR
median is the trigger to revisit §5 of the Phase 6 findings.

If a fill lands at or below the engine's stop (a gap through the stop
overnight), do not enter — the signal is void for that session, and the
Pine will re-signal if the setup is still valid at the next close.

---

## Backward compatibility

The engine's payload is dual-form on purpose: `stop`, `price`, `strategy` and
`comment` are fields the current model already accepts, so **item 1 works before
any of items 3–7 land**. Ship the patch in that order.
