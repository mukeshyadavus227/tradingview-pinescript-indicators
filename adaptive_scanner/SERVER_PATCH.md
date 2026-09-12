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
  Suggested: `INTRADAY 5min / SWING 90min / POSITIONAL 8h / LONGTERM 48h`.
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

---

## Backward compatibility

The engine's payload is dual-form on purpose: `stop`, `price`, `strategy` and
`comment` are fields the current model already accepts, so **item 1 works before
any of items 3–7 land**. Ship the patch in that order.
