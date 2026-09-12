"""
Desired-state reconciler — turns a payload's `desired_state` plus the broker's
actual position/orders into the minimal order diff. Idempotent: applying the
same desired state twice yields no orders the second time.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional
from .schema import SignalV2

TICK = 0.01


@dataclass(frozen=True)
class BrokerPosition:
    symbol: str
    qty: int               # shares, long positive
    avg_price: float = 0.0


@dataclass(frozen=True)
class BrokerOrder:
    order_id: str
    symbol: str
    kind: Literal["STOP", "LIMIT"]
    price: float
    qty: int


@dataclass(frozen=True)
class OrderIntent:
    action: Literal["PLACE_ENTRY", "PLACE_STOP", "REPLACE_STOP", "PLACE_LIMIT", "CANCEL", "SELL_QTY", "FLATTEN", "NOTE"]
    symbol: str
    qty: int = 0
    price: Optional[float] = None
    order_id: Optional[str] = None
    note: str = ""


def _same(a: Optional[float], b: Optional[float]) -> bool:
    return a is not None and b is not None and abs(a - b) <= TICK + 1e-9


def reconcile(sig: SignalV2, pos: Optional[BrokerPosition], orders: list[BrokerOrder], entry_qty: int,
              full_qty: Optional[int] = None) -> list[OrderIntent]:
    """
    entry_qty: the executor's risk-sized share count for a NEW entry (the
    reconciler never sizes).
    full_qty:  the share count originally entered for an OPEN position. The
    executor knows it and should pass it; broker qty alone cannot distinguish
    "100 shares, partial missed" from "100 shares = half of 200". Without it
    the reconciler assumes no partial was missed.
    """
    ds = sig.desired_state
    sym = sig.symbol
    out: list[OrderIntent] = []
    held = pos.qty if pos else 0
    stops = [o for o in orders if o.kind == "STOP"]
    limits = [o for o in orders if o.kind == "LIMIT"]

    if ds is None:
        return [OrderIntent("NOTE", sym, note="no desired_state on payload; v1 path")]

    if ds.side == "FLAT":
        for o in orders:
            out.append(OrderIntent("CANCEL", sym, order_id=o.order_id))
        if held > 0:
            out.append(OrderIntent("FLATTEN", sym, qty=held, note=f"engine says FLAT ({sig.event})"))
        return out

    # ── desired LONG ──
    if held <= 0:
        if sig.is_entry:
            out.append(OrderIntent("PLACE_ENTRY", sym, qty=entry_qty, note=f"{ds.strategy} entry_ref {ds.entry_ref}"))
            if ds.stop is not None:
                out.append(OrderIntent("PLACE_STOP", sym, qty=entry_qty, price=ds.stop))
            if ds.partial_at is not None and ds.partial_pct > 0:
                out.append(OrderIntent("PLACE_LIMIT", sym, qty=max(1, round(entry_qty * ds.partial_pct / 100)), price=ds.partial_at))
            return out
        return [OrderIntent("NOTE", sym, note=f"{sig.event} for a position the broker does not hold — not chasing; check fills")]

    # position exists: reconcile size, stop, partial limit
    # infer full size: if no partial has filled the broker holds 100%; otherwise size_pct_open of full
    full = full_qty if full_qty else (held if ds.size_pct_open >= 99.5 else round(held / max(ds.size_pct_open, 1.0) * 100.0))
    expected = round(full * ds.size_pct_open / 100.0)
    if held > expected:
        out.append(OrderIntent("SELL_QTY", sym, qty=held - expected, note="partial should have filled (engine says size_pct_open=%.0f)" % ds.size_pct_open))
    working_qty = expected if expected > 0 else held

    if ds.stop is not None:
        if not stops:
            out.append(OrderIntent("PLACE_STOP", sym, qty=working_qty, price=ds.stop))
        else:
            s = stops[0]
            if not _same(s.price, ds.stop) or s.qty != working_qty:
                out.append(OrderIntent("REPLACE_STOP", sym, qty=working_qty, price=ds.stop, order_id=s.order_id))
            for extra in stops[1:]:
                out.append(OrderIntent("CANCEL", sym, order_id=extra.order_id))

    if ds.partial_at is not None and ds.size_pct_open >= 99.5:
        want = max(1, round(full * ds.partial_pct / 100.0))
        if not limits:
            out.append(OrderIntent("PLACE_LIMIT", sym, qty=want, price=ds.partial_at))
        elif not _same(limits[0].price, ds.partial_at):
            out.append(OrderIntent("CANCEL", sym, order_id=limits[0].order_id))
            out.append(OrderIntent("PLACE_LIMIT", sym, qty=want, price=ds.partial_at))
    else:
        for o in limits:
            out.append(OrderIntent("CANCEL", sym, order_id=o.order_id, note="partial done or not applicable"))
    return out
