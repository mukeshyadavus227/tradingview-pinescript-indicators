"""
Schema 2.1.0 — the payload asr_engine.pine v3 emits.

Backward compatible with the v1 TVSignal fields; every new field is optional
so an old alert still validates. `extra="ignore"` so a newer script against
an older server degrades rather than fails.
"""
from __future__ import annotations
import hashlib
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_FLOOR = (2, 1, 0)   # reject alerts created before the exit engine existed


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    type: Literal["ENTRY", "SCALE", "MODIFY", "EXIT", "HEARTBEAT"]
    price: Optional[float] = None
    stop: Optional[float] = None
    partial_at: Optional[float] = None
    partial_pct: Optional[int] = None
    pct: Optional[int] = None
    reason: Optional[str] = None
    from_: Optional[float] = Field(default=None, alias="from")


class Trail(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str = "CHANDELIER_ATR"
    k: float = 3.0
    active: bool = False
    level: Optional[float] = None


class DesiredState(BaseModel):
    model_config = ConfigDict(extra="ignore")
    side: Literal["LONG", "FLAT"]
    strategy: str = "None"
    entry_ref: float
    risk: float
    stop: Optional[float] = None
    size_pct_open: float = 0.0
    partial_at: Optional[float] = None
    partial_pct: int = 50
    trail: Trail = Trail()
    breakeven_after_partial: bool = True
    time_stop_at: Optional[int] = None
    bars_in_trade: int = 0


class Meta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bar_time: int
    bar_close_time: Optional[int] = None
    tf: str = ""
    warmup_ok: bool = True
    script_version: str = ""


class SignalV2(BaseModel):
    """Superset of the v1 TVSignal. Old fields keep their names and defaults."""
    model_config = ConfigDict(extra="ignore")
    # v1 fields
    symbol: str
    action: Literal["BUY", "SELL", "MANAGE"]
    qty: float = 1.0
    order_type: str = "MKT"
    price: float = 0.0
    stop: float = 0.0
    tif: str = "DAY"
    sec_type: str = "STK"
    exchange: str = ""
    strategy: str = ""
    comment: str = ""
    # v2 / v2.1
    schema_version: str = "1.0.0"
    signal_id: Optional[str] = None
    profile: Optional[str] = None
    account_route: Optional[str] = None
    manual_only: bool = False
    event: Optional[Literal["ENTRY", "SCALE", "MODIFY", "EXIT", "HEARTBEAT"]] = None
    events: list[Event] = []
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    desired_state: Optional[DesiredState] = None
    meta: Optional[Meta] = None

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _gates(self):
        if self.schema_version != "1.0.0" and _vt(self.schema_version) < SCHEMA_FLOOR:
            raise ValueError(f"stale alert: schema {self.schema_version} < floor {'.'.join(map(str, SCHEMA_FLOOR))} — re-create the TradingView alert")
        if self.meta is not None and self.meta.warmup_ok is False:
            raise ValueError("warmup_ok=false: regime/percentiles not yet valid on this chart")
        if self.action == "MANAGE" and self.event in (None, "ENTRY"):
            raise ValueError("action=MANAGE requires a lifecycle event")
        return self

    @property
    def idempotency_key(self) -> str:
        return hashlib.sha1((self.signal_id or f"{self.symbol}|{self.action}|{self.stop}|{self.price}").encode()).hexdigest()

    @property
    def is_entry(self) -> bool:
        return self.action == "BUY" and (self.event in (None, "ENTRY"))
