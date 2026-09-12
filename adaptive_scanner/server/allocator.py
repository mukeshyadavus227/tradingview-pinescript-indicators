"""
Slot allocator — decides which candidate entries get a position in a shared
risk budget. This module is imported by research/portfolio_sim.py, so the
rule validated in Phase 4 and the rule the server runs are the same code.

Phase 4 results (48 symbols, 2015-2026, 1% risk, cap 10):
  - one position per SYMBOL across profiles is the rule that helps everywhere
  - arrival order with a per-bar-expectancy tiebreak ("per_bar") ≈ FIFO, both
    beat "priority by per-trade expectancy" (which lets slow POSITIONAL trades
    hog slots) and "reserve" (lowest drawdown, lowest return)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

Rule = Literal["fifo", "per_bar", "priority", "reserve"]

# Validated expectancy per bar held (R / bar): S1 0.06, S4-SWING 0.012, S3 0.012, S4-POSITIONAL 0.006.
PER_BAR_RANK = {"S1-SW": 0, "S4-SW": 1, "S3-SW": 2, "S4-POS": 3}
# Validated expectancy per trade: S1 +0.43, S4-POS +0.34, S4-SW +0.28, S3 +0.24.
PRIORITY_RANK = {"S1-SW": 0, "S4-POS": 1, "S4-SW": 2, "S3-SW": 3}


def strategy_key(profile: str, strategy: str) -> str:
    """Map (profile, strategy name or S-number) to the allocator's key."""
    s = str(strategy)
    k = "S1" if ("1" in s or "MeanRev" in s) else "S3" if ("3" in s or "Momentum" in s) else "S4" if ("4" in s or "MultiTF" in s or "MTF" in s) else "S?"
    return f"{k}-{'POS' if profile.upper().startswith('POS') else 'SW'}"


@dataclass(frozen=True)
class Candidate:
    symbol: str
    profile: str
    strategy_key: str
    score: float = 0.0
    signal_id: str = ""


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    profile: str
    strategy_key: str
    risk_dollars: float


@dataclass(frozen=True)
class AllocatorConfig:
    max_positions: int = 10
    risk_pct: float = 1.0            # % of current equity at risk per trade
    max_heat_pct: float = 10.0       # sum of open risk / equity
    one_per_symbol: bool = True
    rule: Rule = "per_bar"


@dataclass(frozen=True)
class Decision:
    candidate: Candidate
    admit: bool
    reason: str
    risk_dollars: float = 0.0


class Allocator:
    def __init__(self, cfg: AllocatorConfig = AllocatorConfig()):
        self.cfg = cfg

    def rank_key(self, c: Candidate):
        if self.cfg.rule in ("priority", "reserve"):
            return (PRIORITY_RANK.get(c.strategy_key, 9), -c.score)
        if self.cfg.rule == "per_bar":
            return (PER_BAR_RANK.get(c.strategy_key, 9), -c.score)
        return (0, -c.score)

    def _reserve_ok(self, c: Candidate, open_positions: list[OpenPosition]) -> bool:
        cap = self.cfg.max_positions
        half = max(1, cap // 2)
        n_open = len(open_positions)
        n_prof = sum(1 for p in open_positions if p.profile == c.profile)
        return n_prof < half or (n_open < cap and n_prof < half + (cap - 2 * half))

    def admit(self, c: Candidate, open_positions: list[OpenPosition], equity: float) -> Decision:
        cfg = self.cfg
        if cfg.one_per_symbol and any(p.symbol == c.symbol for p in open_positions):
            return Decision(c, False, "symbol already held")
        if cfg.rule == "reserve":
            if not self._reserve_ok(c, open_positions):
                return Decision(c, False, "profile reservation full")
        elif len(open_positions) >= cfg.max_positions:
            return Decision(c, False, f"slots full ({cfg.max_positions})")
        risk = equity * cfg.risk_pct / 100.0
        heat = sum(p.risk_dollars for p in open_positions) + risk
        if heat > equity * cfg.max_heat_pct / 100.0 + 1e-9:
            return Decision(c, False, f"heat cap ({cfg.max_heat_pct}%)")
        return Decision(c, True, "admitted", risk)

    def admit_batch(self, candidates: Iterable[Candidate], open_positions: list[OpenPosition], equity: float) -> list[Decision]:
        """Same-bar candidates: rank, then admit sequentially so each admission counts against the next."""
        opens = list(open_positions)
        out = []
        for c in sorted(candidates, key=self.rank_key):
            d = self.admit(c, opens, equity)
            out.append(d)
            if d.admit:
                opens.append(OpenPosition(c.symbol, c.profile, c.strategy_key, d.risk_dollars))
        return out
