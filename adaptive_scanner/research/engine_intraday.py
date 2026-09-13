"""
Python mirror of the INTRADAY_15M profile — written BEFORE the Pine, validated,
then ported. Same discipline as Phases 2-3.

Bars: 15m, RTH only (26 bars per session, 09:30 → 15:45 opens, exchange time).
Daily context comes from the daily bars in research/data and is mapped to the
PRIOR COMPLETED session, which is what request.security("D", expr[1],
lookahead_on) resolves to on an intraday chart.

Causality rules every feature obeys (the adversarial review checks these):
  - anything "per slot across days" (time-of-day volume) is updated AFTER the
    bar's own value is computed, so a bar never sees its own day
  - session-anchored quantities (VWAP, cumulative volume, opening range) use
    bars from the session open up to and including the current bar
  - the opening range is only usable from the bar AFTER it completes
  - daily context is yesterday's, never today's

Sub-strategies (long only):
  S5  Opening-range breakout: first close above the 30-minute OR high, with
      cumulative time-of-day relative volume, OR width in a sane ATR band,
      and daily-trend agreement.
  S6  VWAP reclaim: close back above session VWAP after ≥ 2 bars below it,
      in an uptrending daily context.
  S3i EMA 9/21 cross on 15m, close above VWAP, daily trend up.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
import pine_ta as ta

NAN = np.nan
ET = "America/New_York"
BARS_PER_DAY = 26


@dataclass(frozen=True)
class IntradayParams:
    or_bars: int = 2                 # opening range = first 2 x 15m = 30 minutes
    or_width_min_atr: float = 0.2    # OR width / daily ATR
    or_width_max_atr: float = 1.2
    orb_rvol_cum_min: float = 1.5    # cumulative time-of-day relative volume at the break
    orb_last_slot: int = 12          # no ORB entries after 12:30
    s6_below_bars: int = 2           # bars below VWAP before a reclaim counts
    s6_rvol_min: float = 1.0
    s3_fast: int = 9
    s3_slow: int = 21
    s3_cross_max: int = 3
    last_entry_slot: int = 22        # no new entries after 15:00 (slot 22 opens 15:00)
    eod_slot: int = 25               # flat at the close of the 15:45 bar
    atr_len: int = 14
    tod_alpha: float = 2.0 / 21.0    # EWMA per slot across days
    stop_cap_pct: float = 0.8        # initial stop never wider than this % of price
    stop_floor_atr: float = 1.0      # nor tighter than this many 15m ATRs
    min_price: float = 5.0
    min_adv_usd: float = 5e6
    mintick: float = 0.01


DEFAULT = IntradayParams()


def session_index(t_unix):
    """(date string, slot 0..25) per bar, exchange time."""
    ts = pd.to_datetime(t_unix, unit="s", utc=True).tz_convert(ET)
    mins = (ts.hour * 60 + ts.minute - (9 * 60 + 30)) // 15
    return np.array(ts.strftime("%Y-%m-%d")), np.asarray(mins, dtype=int)


def daily_context_for(daily: pd.DataFrame, dates: np.ndarray):
    """Prior completed daily bar's features, mapped to each intraday bar's session date."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d.t.values, unit="s", utc=True).tz_convert(ET).strftime("%Y-%m-%d").values
    o, h, l, c, v = (d[k].values.astype(float) for k in "ohlcv")
    feats = pd.DataFrame({
        "date": d.date.values,
        "dAtr": ta.atr(h, l, c, 14), "dSma50": ta.sma(c, 50), "dSma200": ta.sma(c, 200),
        "dAdvUsd": ta.sma(v, 20) * c, "dHi20": ta.highest(h, 20), "dLo20": ta.lowest(l, 20),
        "dClose": c, "dHigh": h, "dLow": l,
        "dRoc20": np.where(ta.shift(c, 20) > 0, (c - ta.shift(c, 20)) / ta.shift(c, 20) * 100, NAN),
    })
    # The context for session D is the LAST daily row with date < D — the last
    # completed session — found by search, so it neither needs a daily row
    # labelled D to exist (live loaders that supply completed days only) nor
    # goes two sessions stale when a date is missing from the daily file.
    # (Adversarial review, Phase 5: both failure modes reproduced and fixed.)
    ddates = pd.Index(feats.date.values)
    uniq = pd.Index(sorted(set(dates)))
    pos = ddates.searchsorted(uniq, side="left") - 1
    rows = feats.drop(columns="date").reset_index(drop=True)
    picked = rows.iloc[np.clip(pos, 0, len(rows) - 1)].reset_index(drop=True)
    picked[pos < 0] = np.nan
    picked.index = uniq
    return picked.reindex(dates)


def run_intraday(bars: pd.DataFrame, daily: pd.DataFrame, spy15: pd.DataFrame, p: IntradayParams = DEFAULT) -> pd.DataFrame:
    o, h, l, c, v = (bars[k].values.astype(float) for k in "ohlcv")
    n = len(c)
    dates, slot = session_index(bars.t.values)
    assert ((slot >= 0) & (slot < BARS_PER_DAY)).all(), "bars outside 09:30-15:45 RTH: filter the feed before running the intraday engine"
    ctx = daily_context_for(daily, dates)
    dAtr, dSma50, dSma200, dAdv, dClose = (ctx[k].values for k in ("dAtr", "dSma50", "dSma200", "dAdvUsd", "dClose"))

    # ── chart-timeframe indicators (continuous across sessions, as Pine computes them) ──
    atr = ta.atr(h, l, c, p.atr_len)
    ema_f, ema_s = ta.ema(c, p.s3_fast), ta.ema(c, p.s3_slow)
    cross_up = ta.crossover(ema_f, ema_s)
    bs_up = ta.barssince(cross_up)
    hlc3 = (h + l + c) / 3.0

    # ── session-anchored: VWAP, bands, cumulative volume, opening range, gap ──
    vwap = np.full(n, NAN); vwsd = np.full(n, NAN); cumv = np.zeros(n)
    or_hi = np.full(n, NAN); or_lo = np.full(n, NAN); day_open = np.full(n, NAN)
    gap_pct = np.full(n, NAN); gap_atr = np.full(n, NAN)
    s_pv = s_pv2 = s_v = 0.0; ohi = olo = NAN; or_seen = 0; dopen = NAN; prev_date = None
    for i in range(n):
        if dates[i] != prev_date:
            s_pv = s_pv2 = s_v = 0.0; ohi = -np.inf; olo = np.inf; or_seen = 0; dopen = o[i]; prev_date = dates[i]
        s_pv += hlc3[i] * v[i]; s_pv2 += hlc3[i] ** 2 * v[i]; s_v += v[i]
        if s_v > 0:
            vwap[i] = s_pv / s_v
            vwsd[i] = np.sqrt(max(0.0, s_pv2 / s_v - vwap[i] ** 2))
        cumv[i] = s_v
        if slot[i] < p.or_bars:
            ohi = max(ohi, h[i]); olo = min(olo, l[i]); or_seen += 1
        # OR is usable only once complete AND every OR bar was actually observed
        # (a session missing its first bars must not fire on a ±inf sentinel)
        if slot[i] >= p.or_bars and or_seen == p.or_bars:
            or_hi[i] = ohi; or_lo[i] = olo
        day_open[i] = dopen
        if not np.isnan(dClose[i]) and dClose[i] > 0:
            gap_pct[i] = (dopen - dClose[i]) / dClose[i] * 100.0
            gap_atr[i] = (dopen - dClose[i]) / dAtr[i] if not np.isnan(dAtr[i]) and dAtr[i] > 0 else NAN

    # ── time-of-day relative volume: EWMA per slot over PRIOR days ──
    # Short sessions (early closes) carry the closing auction in a mid-day slot;
    # their bars are read but do not update the slot averages (exchange calendar
    # in Pine; session length in the backtest).
    sess_len = pd.Series(slot).groupby(dates).transform("size").values
    slot_ewma = np.full(BARS_PER_DAY, NAN); cum_ewma = np.full(BARS_PER_DAY, NAN)
    rvol_tod = np.full(n, NAN); rvol_cum = np.full(n, NAN)
    for i in range(n):
        s = slot[i]
        if 0 <= s < BARS_PER_DAY:
            if not np.isnan(slot_ewma[s]) and slot_ewma[s] > 0:
                rvol_tod[i] = v[i] / slot_ewma[s]
            if not np.isnan(cum_ewma[s]) and cum_ewma[s] > 0:
                rvol_cum[i] = cumv[i] / cum_ewma[s]
            # update AFTER use — the bar never sees its own day
            if sess_len[i] == BARS_PER_DAY:
                slot_ewma[s] = v[i] if np.isnan(slot_ewma[s]) else slot_ewma[s] + p.tod_alpha * (v[i] - slot_ewma[s])
                cum_ewma[s] = cumv[i] if np.isnan(cum_ewma[s]) else cum_ewma[s] + p.tod_alpha * (cumv[i] - cum_ewma[s])

    # ── relative strength vs SPY (session-anchored and 20-bar) ──
    spy = spy15.set_index("t").reindex(bars.t.values)
    sc, so_ = spy.c.values.astype(float), spy.o.values.astype(float)
    spy_open = np.full(n, NAN); prev_date = None; so = NAN
    for i in range(n):
        if dates[i] != prev_date:
            so = so_[i]; prev_date = dates[i]          # SPY's session OPEN, mirroring the symbol's day_open
        spy_open[i] = so
    with np.errstate(invalid="ignore", divide="ignore"):
        rs_sess = (c / day_open) / (sc / spy_open) - 1.0
        c20, s20 = ta.shift(c, 20), ta.shift(sc, 20)
        rs_20 = (c / c20) / (sc / s20) - 1.0

    # ── daily-context gates ──
    trend_up = ~np.isnan(dSma200) & (c > dSma200)
    trend_strong = trend_up & ~np.isnan(dSma50) & (dSma50 > dSma200)
    liquidity = ~np.isnan(dAdv) & (dAdv >= p.min_adv_usd) & (c >= p.min_price)
    with np.errstate(invalid="ignore", divide="ignore"):
        or_width_atr = (or_hi - or_lo) / dAtr

    # ── S5: opening-range breakout (first qualifying close above OR high, once per day) ──
    s5_raw = (slot >= p.or_bars) & (slot <= p.orb_last_slot) & (c > or_hi) & ~np.isnan(or_hi)
    s5_trig = np.zeros(n, bool); prev_date = None; fired = False
    for i in range(n):
        if dates[i] != prev_date:
            prev_date = dates[i]; fired = False
        if s5_raw[i] and not fired:
            s5_trig[i] = True; fired = True
    with np.errstate(invalid="ignore"):
        s5_elig = (s5_trig & (rvol_cum >= p.orb_rvol_cum_min) & (or_width_atr >= p.or_width_min_atr) &
                   (or_width_atr <= p.or_width_max_atr) & trend_up)

    # ── S6: VWAP reclaim after ≥ k bars below, uptrend, volume ──
    below = ~np.isnan(vwap) & (c < vwap)
    run_below = np.zeros(n, int); prev_date = None
    for i in range(n):
        if dates[i] != prev_date:
            prev_date = dates[i]; run_below[i] = 1 if below[i] else 0
        else:
            run_below[i] = run_below[i - 1] + 1 if below[i] else 0
    prev_run = ta.shift(run_below.astype(float), 1)
    same_day = np.r_[False, dates[1:] == dates[:-1]]
    with np.errstate(invalid="ignore"):
        s6_trig = same_day & ~below & ~np.isnan(vwap) & (prev_run >= p.s6_below_bars) & (slot >= p.or_bars) & (slot <= p.last_entry_slot)
        s6_elig = s6_trig & trend_up & (rvol_tod >= p.s6_rvol_min)

    # ── S3i: recent EMA cross, above VWAP, uptrend ──
    with np.errstate(invalid="ignore"):
        s3_trig = same_day & ~np.isnan(bs_up) & (bs_up <= p.s3_cross_max) & (bs_up <= slot) & (c > vwap) & (slot >= p.or_bars) & (slot <= p.last_entry_slot)
        s3_elig = s3_trig & trend_up

    # ── initial stops: strategy geometry, floored and capped ──
    cap = c * p.stop_cap_pct / 100.0
    floor_ = atr * p.stop_floor_atr
    s5_stopD = np.clip(c - (or_lo - 0.1 * atr), floor_, cap)
    s6_stopD = np.clip(np.maximum(c - (vwap - 0.5 * atr), 1.2 * atr), floor_, cap)
    s3_stopD = np.clip(1.5 * atr, floor_, cap)

    # ── priority selection: S5 > S6 > S3i (validated later; provisional) ──
    best = np.where(s5_elig, 5, np.where(s6_elig, 6, np.where(s3_elig, 3, 0)))
    stopD = np.select([best == 5, best == 6], [s5_stopD, s6_stopD], s3_stopD)
    entry = ta.round_to_mintick(c, p.mintick)
    stop = ta.round_to_mintick(c - stopD, p.mintick)
    risk = np.abs(entry - stop)
    tp = ta.round_to_mintick(c + 2.0 * risk, p.mintick)          # reference 2R target for the fixed-target exit model

    # index of the last bar of each session (EOD flat target). This is a label
    # rule, not a feature: "flat at the session's last bar" is causal at that
    # bar (session.islastbar / the exchange calendar in Pine).
    eod_idx = np.full(n, -1)
    last_of_day = {}
    for i in range(n):
        last_of_day[dates[i]] = i
    for i in range(n):
        eod_idx[i] = last_of_day[dates[i]]
    bars_left = eod_idx - np.arange(n)

    warm = (np.arange(n) >= 60) & ~np.isnan(atr) & ~np.isnan(dAtr) & ~np.isnan(dSma200) & ~np.isnan(rvol_cum)
    # Entries are gated RELATIVE to the session end (≥ 3 bars left), so an early
    # close cannot admit a trade on its last bars and hold it overnight.
    eligible = warm & (best > 0) & liquidity & (slot <= p.last_entry_slot) & (bars_left >= 3) & (risk > 0)

    out = pd.DataFrame({
        "t": bars.t.values, "date": dates, "slot": slot, "o": o, "h": h, "l": l, "c": c, "v": v,
        "atr": atr, "vwap": vwap, "vwsd": vwsd, "or_hi": or_hi, "or_lo": or_lo, "or_width_atr": or_width_atr,
        "gap_pct": gap_pct, "gap_atr": gap_atr, "rvol_tod": rvol_tod, "rvol_cum": rvol_cum,
        "rs_sess": rs_sess, "rs_20": rs_20, "trend_up": trend_up, "trend_strong": trend_strong,
        "dAtr": dAtr, "dSma200": dSma200, "dAdvUsd": dAdv, "dRoc20": ctx["dRoc20"].values,
        "s5_trig": s5_trig, "s5_elig": s5_elig, "s6_trig": s6_trig, "s6_elig": s6_elig, "s3_trig": s3_trig, "s3_elig": s3_elig,
        "s5_stopD": s5_stopD, "s6_stopD": s6_stopD, "s3_stopD": s3_stopD,
        "best": best, "entry": entry, "stop": stop, "risk": risk, "tp": tp, "eligible": eligible, "eod_idx": eod_idx, "bars_left": bars_left,
        "liquidity": liquidity, "warm": warm,
    })
    return out


STRAT_NAMES_I = {5: "S5_ORB", 6: "S6_VWAP_reclaim", 3: "S3i_EMA_cross"}
