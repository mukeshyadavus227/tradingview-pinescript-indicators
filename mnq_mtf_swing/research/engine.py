"""
Python mirror of mnq_mtf_swing.pine — the MNQ 4H -> 1H -> 15M long-only swing engine.

This file IS the rule specification in executable form. The Pine indicator is a
line-for-line port of the functions below; README.md restates the rules in
prose. If the two ever disagree, the mirror plus its tests decide.

Conventions
-----------
* Bars are 15M, index 0 oldest, `t` = bar OPEN time (Unix s, UTC).
* Every rule runs once per CLOSED 15M bar. The only intrabar dependence is the
  SL/TP touch on bars after the entry bar (open gap -> fill at open, else the
  level; when both SL and TP are touched in one bar the STOP WINS. That is a
  deliberate, conservative divergence from adaptive_scanner/research/labels.py,
  which resolves the same bar with an open-to-nearer-extreme heuristic).
* Higher-timeframe (HTF) values for 15M bar i are read from the LAST CLOSED
  HTF bar (`map_idx[i] - 1`), which is exactly what
  `request.security(sym, "240"/"60", f()[1], lookahead = barmerge.lookahead_on)`
  returns. The HTF bar that closes at the same instant as bar i is NOT visible
  on bar i; it becomes visible on i + 1.
* Prices are rounded to the tick (0.25) BEFORE any risk/reward comparison.

State machine (15M): IDLE -> AT_ZONE -> REJECTED -> HL_OK -> IN_TRADE -> IDLE.
Within one closed bar the evaluation order is fixed:
  (0) IN_TRADE exit branch (only if the bar STARTED in trade; an exit bar never re-arms)
  (1) global resets for states 1..3 (4H lost, 1H trend lost, close below Zinv, weekend gap)
  (2) arm (IDLE -> AT_ZONE) when a zone candidate is tested
  (3) 15M pivot-low step (a pivot confirmed on this bar may promote REJECTED -> HL_OK or raise HL)
  (4) the AT_ZONE block (track the low, leave-zone, timeout, rejection candle)
  (5) undercut checks (low below RL / below HL)
  (6) stage timeout
  (7) break -> entry gate
A bar may pass IDLE -> AT_ZONE -> REJECTED, or REJECTED -> HL_OK -> IN_TRADE, in one pass.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from bars import Bars, aggregate
from ta import atr, ema, pivots, sma

CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

IDLE, AT_ZONE, REJECTED, HL_OK, IN_TRADE = 0, 1, 2, 3, 4
STATE_NAMES = {IDLE: "IDLE", AT_ZONE: "AT_ZONE", REJECTED: "REJECTED", HL_OK: "HL_OK", IN_TRADE: "IN_TRADE"}

# ---- constants (design choices, not inputs; see README "Constants") ----
ATR_LEN = 14          # every ATR
H24_LEN = 24          # 1H bars: the high the pullback came from
PULLBACK_ATR = 0.5    # S2: H24 - C1 >= 0.5 x ATR1
VOL_FAST, VOL_SLOW = 5, 20
RING_K = 8            # pivots kept per side per timeframe; this depth IS the age bound
FLOOR_ATR15 = 0.5     # minimum risk = max(0.5 x ATR15, 4 ticks)
FLOOR_TICKS = 4
MERGE_ATR1 = 0.25     # TP candidates closer than this collapse
TP_OFFSET_TICKS = 2   # TP sits 2 ticks under the level
SL_OFFSET_TICKS = 1   # SL sits 1 tick under the anchor
ZONE_LEAVE_TOL = 2.0  # AT_ZONE ends when close > z* + 2 tol without a rejection
WEEKEND_GAP_MIN = 120    # a bar gap longer than this is a weekend/holiday
WARM_15M_BARS = 100


@dataclass
class Params:
    ema_fast: int = 20
    ema_slow: int = 50
    piv_htf: int = 3
    piv_ltf: int = 2
    zone_tol_atr: float = 0.5
    stage_timeout_bars: int = 16
    min_rr: float = 1.5
    fallback_rr: float = 2.0
    max_risk_atr: float = 2.0      # 0 = off
    vol_filter: bool = False
    # Entry-session filter is OFF by default: this is a swing engine on a
    # 23-hour contract, held overnight, so a break at 03:00 CT is as valid as
    # one at 10:00. Turning it on restricts entries to [start, end) Chicago
    # wall time. Entries into the 16:00-17:00 CT halt are always deferred.
    session_filter: bool = False
    entry_session: tuple = ("0830", "1500")   # exchange (Chicago) wall time, [start, end)
    roll_block_days: int = 3       # 0 = off
    tick: float = 0.25


def rt(x: float, tick: float) -> float:
    """Round to the nearest tick, ties away from zero (math.round_to_mintick)."""
    return math.floor(x / tick + 0.5) * tick if x >= 0 else -math.floor(-x / tick + 0.5) * tick


# --------------------------------------------------------------------------------------
# HTF context: per-HTF-bar features plus causal pivot rings
# --------------------------------------------------------------------------------------
@dataclass
class Piv:
    price: float
    idx: int          # HTF bar index of the extreme
    broken: bool = False


@dataclass
class HTFContext:
    bars: Bars
    map_idx: np.ndarray
    close: np.ndarray
    ema_f: np.ndarray
    ema_s: np.ndarray
    atr: np.ndarray
    h24: np.ndarray
    sma_v_fast: np.ndarray
    sma_v_slow: np.ndarray
    prov_high: np.ndarray                 # highest high over the last piv_htf bars (incl. current)
    ph_rings: list = field(default_factory=list)   # per bar: list[Piv], most recent first
    pl_rings: list = field(default_factory=list)


def build_htf(bars15: Bars, minutes: int, p: Params) -> HTFContext:
    hb, map_idx = aggregate(bars15, minutes)
    n = len(hb)
    ema_f = ema(hb.c, p.ema_fast)
    ema_s = ema(hb.c, p.ema_slow)
    a = atr(hb.h, hb.l, hb.c, ATR_LEN)
    h24 = np.full(n, np.nan)
    prov = np.full(n, np.nan)
    for j in range(n):
        if j >= H24_LEN - 1:
            h24[j] = hb.h[j - H24_LEN + 1 : j + 1].max()
        if j >= p.piv_htf - 1:
            prov[j] = hb.h[j - p.piv_htf + 1 : j + 1].max()
    svf = sma(hb.v, VOL_FAST)
    svs = sma(hb.v, VOL_SLOW)
    ph, pl, ph_idx, pl_idx = pivots(hb.h, hb.l, p.piv_htf, p.piv_htf)

    ph_rings, pl_rings = [], []
    ring_h: list[Piv] = []
    ring_l: list[Piv] = []
    for j in range(n):
        # (a) push the pivot confirmed on this bar (idempotent: keyed by extreme index)
        if ph_idx[j] >= 0 and (not ring_h or ring_h[0].idx != ph_idx[j]):
            ring_h.insert(0, Piv(float(ph[j]), int(ph_idx[j])))
            del ring_h[RING_K:]
        if pl_idx[j] >= 0 and (not ring_l or ring_l[0].idx != pl_idx[j]):
            ring_l.insert(0, Piv(float(pl[j]), int(pl_idx[j])))
            del ring_l[RING_K:]
        # (b) "broken" = some HTF close after confirmation exceeded price + tol (sticky)
        tol_j = p.zone_tol_atr * a[j] if not np.isnan(a[j]) else np.nan
        for pv in ring_h:
            if not pv.broken and j > pv.idx + p.piv_htf and not np.isnan(tol_j) and hb.c[j] > pv.price + tol_j:
                pv.broken = True
        ph_rings.append([Piv(x.price, x.idx, x.broken) for x in ring_h])
        pl_rings.append([Piv(x.price, x.idx, x.broken) for x in ring_l])
    return HTFContext(hb, map_idx, hb.c, ema_f, ema_s, a, h24, svf, svs, prov, ph_rings, pl_rings)


def in_window(rings: list[Piv], ref: int) -> list[Piv]:
    """Pivots usable at reference bar `ref`.

    The ring depth (RING_K) is the only bound: a support or resistance level
    does not expire just because it is old, and an extra age cutoff was a
    second knob measuring the same thing.
    """
    return list(rings)


# --------------------------------------------------------------------------------------
# calendar helpers (both platforms compute these from the bar time only)
# --------------------------------------------------------------------------------------
def third_friday(y: int, m: int) -> date:
    d = date(y, m, 15)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


def next_expiry(d: date) -> date:
    for m in (3, 6, 9, 12):
        if m >= d.month:
            e = third_friday(d.year, m)
            if e >= d:
                return e
    return third_friday(d.year + 1, 3)


def in_roll_window(t_unix: int, roll_block_days: int) -> bool:
    if roll_block_days <= 0:
        return False
    d = datetime.fromtimestamp(int(t_unix), CT).date()   # exchange timezone, as in Pine
    return (next_expiry(d) - d).days <= roll_block_days


def in_entry_session(t_unix: int, session: tuple) -> bool:
    local = datetime.fromtimestamp(int(t_unix), CT)
    hm = local.hour * 100 + local.minute
    s, e = int(session[0]), int(session[1])
    return s <= hm < e


def is_last_bar_of_session(t_unix: int) -> bool:
    """The 15M bar that closes into the 16:00-17:00 CT daily maintenance halt.

    A market order at that close has no market to fill in, so an entry there is
    deferred rather than sent. Computed from the bar's own exchange-local open
    time on both platforms.
    """
    local = datetime.fromtimestamp(int(t_unix), CT)
    return local.hour == 15 and local.minute == 45


# --------------------------------------------------------------------------------------
# the engine
# --------------------------------------------------------------------------------------
@dataclass
class Trade:
    entry_bar: int
    entry_time: int
    entry: float
    sl: float
    tp: float
    risk: float
    rr: float
    sl_source: str
    tp_source: str
    tp_level: float
    zone_kind: str
    zone_level: float
    zinv: float
    rl: float
    hl: float
    sh: float
    arm_bar: int
    exit_bar: int = -1
    exit_time: int = -1
    exit_price: float = np.nan
    exit_reason: str = ""
    r: float = np.nan


@dataclass
class Result:
    state: np.ndarray            # state at the END of each 15M bar
    block: list                  # dashboard BLOCK reason per bar
    trades: list
    events: list                 # dicts: bar, time, type, reason, ...
    warm_ok_bar: int


def run(bars15: Bars, p: Params | None = None) -> Result:
    p = p or Params()
    n = len(bars15)
    tick = p.tick
    o, h, l, c, t = bars15.o, bars15.h, bars15.l, bars15.c, bars15.t
    h4 = build_htf(bars15, 240, p)
    h1 = build_htf(bars15, 60, p)
    atr15 = atr(h, l, c, ATR_LEN)
    _, pl15, _, pl15_idx = pivots(h, l, p.piv_ltf, p.piv_ltf)

    state_arr = np.zeros(n, dtype=int)
    block = [""] * n
    trades: list[Trade] = []
    events: list[dict] = []
    warm_ok_bar = -1

    # persistent state
    state = IDLE
    z_star = tol_star = zinv = np.nan
    kind_star = ""
    arm_bar = rl_bar = hl_bar = stage_bar = entry_bar = -1
    rl = hl = sh = np.nan
    last_event_bar = -1
    guard_ref1 = -1          # arming blocked until ref1 != guard_ref1
    cur: Trade | None = None

    def ev(i, typ, **kw):
        d = dict(bar=int(i), time=int(t[i]), type=typ)
        d.update(kw)
        events.append(d)

    for i in range(n):
        r4 = h4.map_idx[i] - 1
        r1 = h1.map_idx[i] - 1

        # ---------- (0) IN_TRADE exit branch ----------
        if state == IN_TRADE:
            assert cur is not None
            if i > entry_bar:
                px, why = np.nan, ""
                if o[i] <= cur.sl:
                    px, why = o[i], "SL_GAP"
                elif o[i] >= cur.tp:
                    px, why = o[i], "TP_GAP"
                elif l[i] <= cur.sl:
                    px, why = cur.sl, "SL"
                elif h[i] >= cur.tp:
                    px, why = cur.tp, "TP"
                elif in_roll_window(t[i], p.roll_block_days) and not is_last_bar_of_session(t[i]):
                    # Force-exit before the quarterly roll: a position held across
                    # the contract change would see a basis jump the rule view
                    # reads as a gap through SL or TP.
                    px, why = c[i], "ROLL"
                if why:
                    cur.exit_bar, cur.exit_time, cur.exit_price, cur.exit_reason = i, int(t[i]), float(px), why
                    cur.r = (px - cur.entry) / cur.risk
                    ev(i, "EXIT", reason=why, price=float(px), r=cur.r)
                    state = IDLE
                    last_event_bar = i
                    guard_ref1 = r1
                    cur = None
            state_arr[i] = state
            if state == IN_TRADE:
                block[i] = "IN_TRADE"
                continue
            block[i] = "EXITED"
            continue  # an exit bar never re-arms

        # ---------- warm-up ----------
        warm = (
            r4 >= 0 and r1 >= 0 and i >= WARM_15M_BARS and not np.isnan(atr15[i])
            and not np.isnan(h4.atr[r4]) and r4 >= 3 and not np.isnan(h4.ema_s[r4 - 3])
            and len(in_window(h4.ph_rings[r4], r4)) >= 2 and len(in_window(h4.pl_rings[r4], r4)) >= 2
            and not np.isnan(h1.atr[r1]) and r1 >= 3 and not np.isnan(h1.ema_s[r1 - 3])
            and len(in_window(h1.pl_rings[r1], r1)) >= 2 and len(in_window(h1.ph_rings[r1], r1)) >= 1
            and not np.isnan(h1.h24[r1]) and not np.isnan(h1.sma_v_slow[r1])
        )
        if not warm:
            state = IDLE
            state_arr[i] = state
            block[i] = "WARMUP"
            continue
        if warm_ok_bar < 0:
            warm_ok_bar = i
            ev(i, "WARM_OK")

        # ---------- 4H regime ----------
        ph4 = in_window(h4.ph_rings[r4], r4)
        pl4 = in_window(h4.pl_rings[r4], r4)
        c4, ef4, es4, es4_3, atr4 = h4.close[r4], h4.ema_f[r4], h4.ema_s[r4], h4.ema_s[r4 - 3], h4.atr[r4]
        R1 = ph4[0].price > ph4[1].price and pl4[0].price > pl4[1].price
        R2 = c4 > es4 and ef4 > es4 and es4 > es4_3
        R3 = c4 > pl4[0].price
        regime4h = R1 and R2 and R3

        # ---------- 1H context ----------
        ph1 = in_window(h1.ph_rings[r1], r1)
        pl1 = in_window(h1.pl_rings[r1], r1)
        c1, ef1, es1, es1_3, atr1 = h1.close[r1], h1.ema_f[r1], h1.ema_s[r1], h1.ema_s[r1 - 3], h1.atr[r1]
        tol = p.zone_tol_atr * atr1
        S1 = ef1 > es1 and es1 > es1_3
        S2 = h1.h24[r1] - c1 >= PULLBACK_ATR * atr1
        S3 = h1.sma_v_fast[r1] < h1.sma_v_slow[r1]
        ctx1h = S1 and S2 and (S3 or not p.vol_filter)

        # zone candidates (price, kind, priority)
        cands = [(ef1, "EMA20", 2), (es1, "EMA50", 3)]
        if len(pl1) >= 2 and pl1[0].price > pl1[1].price:
            cands.append((pl1[0].price, "PL", 0))
        brk = None
        for pv in ph1:
            if pv.broken and pv.price < c1 and pv.price >= es1 - 2 * tol:
                brk = pv.price
                break
        if brk is not None:
            cands.append((brk, "BRK", 1))

        # ---------- (1) global resets ----------
        if state in (AT_ZONE, REJECTED, HL_OK):
            reason = ""
            if not regime4h:
                reason = "4H_LOST"
            elif not S1:
                reason = "1H_TREND_LOST"
            elif c[i] < zinv:
                reason = "INVALIDATED"
            elif i > 0 and (t[i] - t[i - 1]) > WEEKEND_GAP_MIN * 60:
                reason = "SESSION_GAP"
            if reason:
                ev(i, "RESET", reason=reason, state=STATE_NAMES[state])
                state = IDLE
                last_event_bar = i
                if reason == "INVALIDATED":
                    guard_ref1 = r1

        def rejection(k):
            return l[k] <= z_star + tol_star and c[k] > z_star and h[k] > l[k] and (c[k] - l[k]) >= 0.5 * (h[k] - l[k])

        # ---------- arm ----------
        if state == IDLE and regime4h and ctx1h and last_event_bar != i and guard_ref1 != r1:
            touched = [(z, k, pr) for (z, k, pr) in cands if l[i] <= z + tol and c[i] >= z - tol]
            if touched:
                # collapse candidates within tol: lower price, highest-priority kind
                touched.sort(key=lambda x: x[0])
                merged = []
                for z, k, pr in touched:
                    if merged and z - merged[-1][0] <= tol:
                        if pr < merged[-1][2]:
                            merged[-1] = (merged[-1][0], k, pr)
                    else:
                        merged.append((z, k, pr))
                z_star, kind_star, _ = merged[0]          # lowest qualifying level
                tol_star = tol
                # The setup is invalid once price closes a full tolerance below
                # the level it was testing. An earlier version also looked down
                # at nearby untouched candidates and pushed the invalidation
                # under the lowest of them; that widened every stop-fallback and
                # was a rule nobody asked for, so it is gone.
                zinv = z_star - tol_star
                arm_bar, rl, rl_bar = i, l[i], i
                state = AT_ZONE
                ev(i, "ARM", level=float(z_star), kind=kind_star, tol=float(tol_star), zinv=float(zinv))

        # ---------- (2) pivot step ----------
        piv_p = pl15_idx[i]  # index of the 15M pivot low confirmed on this bar, or -1
        if state == REJECTED and piv_p > rl_bar and pl15[i] > rl and pl15[i] >= zinv:
            hl, hl_bar = pl15[i], piv_p
            sh = h[rl_bar:piv_p].max()
            state = HL_OK
            stage_bar = i
            ev(i, "HL", hl=float(hl), sh=float(sh))
        elif state == HL_OK and piv_p > hl_bar and pl15[i] > hl:
            hl, hl_bar = pl15[i], piv_p
            sh = max(sh, h[rl_bar:piv_p].max())
            ev(i, "HL_RAISE", hl=float(hl), sh=float(sh))

        # ---------- AT_ZONE ----------
        if state == AT_ZONE:
            if l[i] < rl:
                rl, rl_bar = l[i], i
            if c[i] > z_star + ZONE_LEAVE_TOL * tol_star:
                ev(i, "RESET", reason="ZONE_LEFT", state="AT_ZONE")
                state = IDLE
                last_event_bar = i
            elif i - arm_bar > p.stage_timeout_bars:
                ev(i, "RESET", reason="TIMEOUT_REJECT", state="AT_ZONE")
                state = IDLE
                last_event_bar = i
            elif rejection(i):
                state = REJECTED
                stage_bar = i
                ev(i, "REJECT", rl=float(rl))

        # ---------- (3)/(4) REJECTED and HL_OK undercut + timeout ----------
        if state in (REJECTED, HL_OK):
            if l[i] < rl:
                # deeper test of the same level: re-reject in place or fall back to AT_ZONE
                rl, rl_bar = l[i], i
                if rejection(i):
                    state = REJECTED
                    stage_bar = i
                    ev(i, "REJECT", rl=float(rl), note="re-reject")
                else:
                    state = AT_ZONE
                    ev(i, "FALLBACK", to="AT_ZONE")
            elif state == HL_OK and l[i] < hl:
                state = REJECTED
                stage_bar = i
                ev(i, "FALLBACK", to="REJECTED")
        if state in (REJECTED, HL_OK) and i - stage_bar > p.stage_timeout_bars:
            reason = "TIMEOUT_HL" if state == REJECTED else "TIMEOUT_BREAK"
            ev(i, "RESET", reason=reason, state=STATE_NAMES[state])
            state = IDLE
            last_event_bar = i
            guard_ref1 = r1

        # ---------- (5) break -> entry gate ----------
        if state == HL_OK:
            if c[i] > sh:
                verdict, info = entry_gate(i, p, o, h, l, c, t, atr15, h4, h1, r4, r1, z_star, tol_star, zinv, hl, ph4, ph1)
                if verdict == "ENTER":
                    cur = Trade(entry_bar=i, entry_time=int(t[i]), entry=info["entry"], sl=info["sl"], tp=info["tp"],
                                risk=info["risk"], rr=info["rr"], sl_source=info["sl_source"], tp_source=info["tp_source"],
                                tp_level=info["tp_level"], zone_kind=kind_star, zone_level=float(z_star), zinv=float(zinv),
                                rl=float(rl), hl=float(hl), sh=float(sh), arm_bar=arm_bar)
                    trades.append(cur)
                    entry_bar = i
                    state = IN_TRADE
                    ev(i, "ENTRY", **{k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in info.items()})
                elif verdict == "DEFER":
                    ev(i, "DEFER", reason=info["reason"])
                    sh = max(sh, h[i])
                else:  # SKIP
                    ev(i, "SKIP", reason=info["reason"])
                    state = IDLE
                    last_event_bar = i
                    guard_ref1 = r1
            else:
                sh = max(sh, h[i])  # ratchet: the most recent 15M high is the reference

        state_arr[i] = state
        # dashboard block reason (single gate, precedence)
        if state == IN_TRADE:
            block[i] = "IN_TRADE"
        elif not R1:
            block[i] = "4H:R1 STRUCT"
        elif not R2:
            block[i] = "4H:R2 TREND"
        elif not R3:
            block[i] = "4H:R3 SUPPORT"
        elif not S1:
            block[i] = "1H:S1 TREND"
        elif not S2:
            block[i] = "1H:S2 PULLBACK"
        elif p.vol_filter and not S3:
            block[i] = "1H:S3 VOL"
        elif state == IDLE and guard_ref1 == r1:
            block[i] = "REARM_GUARD"
        elif state == IDLE:
            block[i] = "1H:NOT_AT_ZONE"
        elif state == AT_ZONE:
            block[i] = "15M:WAIT_REJECT"
        elif state == REJECTED:
            block[i] = "15M:WAIT_HL"
        else:
            block[i] = "15M:WAIT_BREAK"

    return Result(state_arr, block, trades, events, warm_ok_bar)


def entry_gate(i, p, o, h, l, c, t, atr15, h4, h1, r4, r1, z_star, tol_star, zinv, hl, ph4, ph1):
    """Pure function of bars. Returns ("ENTER"|"DEFER"|"SKIP", info)."""
    tick = p.tick
    if is_last_bar_of_session(t[i]):
        return "DEFER", {"reason": "SESSION_LAST_BAR"}
    if p.session_filter and not in_entry_session(t[i], p.entry_session):
        return "DEFER", {"reason": "OUTSIDE_ENTRY_SESSION"}
    if in_roll_window(t[i], p.roll_block_days):
        return "SKIP", {"reason": "ROLL_WINDOW"}
    entry = rt(c[i], tick)

    # ---- stop (4.1) ----
    # The user's primary rule: 1 tick below the 15M higher low. The 1H setup
    # invalidation (zone floor) is the FALLBACK, used only when the higher-low
    # stop is tighter than the noise floor. An earlier draft swapped in the zone
    # floor whenever the higher low sat inside the zone band; that fired on
    # almost every setup, made every stop a zone-width stop, and the risk cap
    # then killed most breaks.
    floor = max(FLOOR_ATR15 * atr15[i], FLOOR_TICKS * tick)
    sl = rt(hl, tick) - SL_OFFSET_TICKS * tick
    sl_source = "HL"
    risk = entry - sl
    if risk < floor:
        sl2 = rt(zinv, tick) - SL_OFFSET_TICKS * tick
        if entry - sl2 >= floor:
            sl, risk, sl_source = sl2, entry - sl2, "1H-INV"
        else:
            return "SKIP", {"reason": "RISK_FLOOR"}
    if p.max_risk_atr > 0 and risk > p.max_risk_atr * h1.atr[r1]:
        return "SKIP", {"reason": "RISK_CAP"}

    # ---- TP candidates (4.2) ----
    h24 = h1.h24[r1]
    strong = [(pv.price, "4H-PH") for pv in ph4] + [(h24, "1H-HIGH")]
    prov = h4.prov_high[r4]
    if not np.isnan(prov) and prov > h4.close[r4]:
        strong.append((prov, "4H-PROV"))
    weak = [(pv.price, "1H-PH") for pv in ph1 if pv.price != h24]
    cands = [(lv, k, True) for lv, k in strong] + [(lv, k, False) for lv, k in weak]
    cands = [x for x in cands if x[0] > entry + (TP_OFFSET_TICKS + 1) * tick]
    cands.sort(key=lambda x: (x[0], not x[2]))
    merged = []
    for lv, k, st in cands:
        if merged and lv - merged[-1][0] <= MERGE_ATR1 * h1.atr[r1]:
            if st and not merged[-1][2]:
                merged[-1] = (merged[-1][0], k, True)
        else:
            merged.append((lv, k, st))

    # ---- TP selection (4.3) ----
    tp, tp_source, tp_level = np.nan, "", np.nan
    for lv, k, st in merged:
        cand = rt(lv, tick) - TP_OFFSET_TICKS * tick
        rr = (cand - entry) / risk
        if rr >= p.min_rr:
            tp, tp_source, tp_level = cand, k, lv
            break
        if st:
            return "SKIP", {"reason": "TP_STRONG_WALL"}
    if np.isnan(tp):
        tp, tp_source, tp_level = rt(entry + p.fallback_rr * risk, tick), "RR", np.nan
    if tp < entry + 2 * tick:
        return "SKIP", {"reason": "GEOMETRY"}
    rr = (tp - entry) / risk
    return "ENTER", dict(entry=entry, sl=sl, tp=tp, risk=risk, rr=rr, sl_source=sl_source, tp_source=tp_source, tp_level=tp_level)


# --------------------------------------------------------------------------------------
def summarize(res: Result) -> dict:
    closed = [tr for tr in res.trades if tr.exit_bar >= 0]
    rs = np.array([tr.r for tr in closed]) if closed else np.array([])
    out = dict(trades=len(res.trades), closed=len(closed))
    if len(rs):
        out.update(mean_r=float(rs.mean()), hit=float((rs > 0).mean()), sum_r=float(rs.sum()),
                   pf=float(rs[rs > 0].sum() / max(1e-9, -rs[rs < 0].sum())) if (rs < 0).any() else float("inf"))
    from collections import Counter
    out["exits"] = dict(Counter(tr.exit_reason for tr in closed))
    out["skips"] = dict(Counter(e["reason"] for e in res.events if e["type"] == "SKIP"))
    out["resets"] = dict(Counter(e["reason"] for e in res.events if e["type"] == "RESET"))
    out["arms"] = sum(1 for e in res.events if e["type"] == "ARM")
    return out


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from bars import load_csv_gz

    path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "data" / "MNQ1_15m.csv.gz")
    res = run(load_csv_gz(path))
    print(json.dumps(summarize(res), indent=1, default=str))
    for tr in res.trades:
        print(f"ENTRY {datetime.fromtimestamp(tr.entry_time, ET):%Y-%m-%d %H:%M} @ {tr.entry} SL {tr.sl} ({tr.sl_source}) "
              f"TP {tr.tp} ({tr.tp_source}) rr {tr.rr:.2f} zone {tr.zone_kind} -> {tr.exit_reason} {tr.r:+.2f}R")
