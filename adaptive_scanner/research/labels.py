"""
Triple-barrier labelling that reproduces the TradingView broker emulator.

For a signal on bar t (entry filled at bar t's close via process_orders_on_close),
the bracket is live from bar t+1. On each subsequent bar the emulator applies:

  1. Gap fills first. A stop order fills at the OPEN if the open is already
     through it; a limit order fills at the OPEN if the open is already through it.
  2. Otherwise, if both the stop and the target are inside the bar's range, the
     intrabar path is assumed to be
         open → high → low → close   if |high − open| < |open − low|
         open → low → high → close   otherwise
     and whichever level the path reaches first is the fill.
  3. A time stop closes at the bar's CLOSE, after 1–2 are checked for that bar.
  4. If the data ends first, the trade is censored at the last close.

Returns per-event: exit index, exit price, reason, bars held, gross R,
MFE/MAE in R, and R net of costs at several round-trip cost levels in bps of
entry price — that is the cost-sensitivity curve.
"""
import numpy as np

REASONS = ("TP", "SL", "TP_GAP", "SL_GAP", "TIME", "EOD")
COST_BPS = (0, 1, 3, 5, 10)


def label_event(o, h, l, c, time_ms, t, is_long, entry, stop, tp, horizon_days):
    n = len(c)
    risk = abs(entry - stop)
    if risk <= 0 or t >= n - 1:
        return None
    sgn = 1.0 if is_long else -1.0
    horizon_ms = horizon_days * 86400000
    mfe = mae = 0.0
    exit_i = exit_p = None
    reason = "EOD"
    for i in range(t + 1, n):
        oi, hi, li, ci = o[i], h[i], l[i], c[i]
        # running excursion in R, measured before any fill on this bar
        mfe = max(mfe, sgn * ((hi if is_long else li) - entry) / risk)
        mae = min(mae, sgn * ((li if is_long else hi) - entry) / risk)
        if is_long:
            gap_sl, gap_tp = oi <= stop, oi >= tp
            hit_sl, hit_tp = li <= stop, hi >= tp
        else:
            gap_sl, gap_tp = oi >= stop, oi <= tp
            hit_sl, hit_tp = hi >= stop, li <= tp
        if gap_sl:
            exit_i, exit_p, reason = i, oi, "SL_GAP"; break
        if gap_tp:
            exit_i, exit_p, reason = i, oi, "TP_GAP"; break
        if hit_sl and hit_tp:
            high_first = abs(hi - oi) < abs(oi - li)
            tp_first = high_first if is_long else not high_first
            if tp_first:
                exit_i, exit_p, reason = i, tp, "TP"
            else:
                exit_i, exit_p, reason = i, stop, "SL"
            break
        if hit_sl:
            exit_i, exit_p, reason = i, stop, "SL"; break
        if hit_tp:
            exit_i, exit_p, reason = i, tp, "TP"; break
        if time_ms[i] - time_ms[t] >= horizon_ms:
            exit_i, exit_p, reason = i, ci, "TIME"; break
    if exit_i is None:
        exit_i, exit_p, reason = n - 1, c[n - 1], "EOD"
    r_gross = sgn * (exit_p - entry) / risk
    out = dict(exit_idx=exit_i, exit_price=exit_p, reason=reason, bars_held=exit_i - t,
               R=r_gross, mfe_R=mfe, mae_R=mae)
    # Round-trip cost expressed in bps of entry, converted to R.
    for bps in COST_BPS:
        out[f"R_net{bps}"] = r_gross - (entry * bps / 1e4) / risk
    return out


def label_events(bars_df, events, horizon_days):
    """events: iterable of dicts with keys t_idx, is_long, entry, stop, tp. Adds label fields in place."""
    o, h, l, c = (bars_df[k].values.astype(float) for k in "ohlc")
    time_ms = bars_df.t.values.astype(np.int64) * 1000
    out = []
    for ev in events:
        lab = label_event(o, h, l, c, time_ms, ev["t_idx"], ev["is_long"], ev["entry"], ev["stop"], ev["tp"], horizon_days)
        if lab is not None:
            out.append({**ev, **lab})
    return out


# ────────────────────────────────────────────────────────────────────────────
# Phase 3 exit models
# ────────────────────────────────────────────────────────────────────────────
# One labeller, parameterised by an ExitModel, so every candidate exit is
# evaluated on the same events with the same fill rules. Stop modifications
# decided at a bar's CLOSE take effect from the NEXT bar, which is how a
# strategy.exit() re-issued on bar close behaves in the Strategy Tester.
from dataclasses import dataclass


@dataclass(frozen=True)
class ExitModel:
    name: str
    partial_r: float = 0.0        # 0 = no partial; else take `partial_frac` off at entry + partial_r * risk
    partial_frac: float = 0.5
    breakeven_after_partial: bool = True
    trail_k: float = 0.0          # 0 = no trail; else chandelier stop = extreme-since-entry -/+ k * ATR
    trail_from: str = "partial"   # "entry" = trail active from bar t+1; "partial" = only once the partial has filled
    remainder_tp: bool = True     # keep the original far target on the remainder
    time_stop: bool = True


INTRADAY_MODELS = [
    ExitModel("I0_fixed2R_eod",        partial_r=0.0, trail_k=0.0, remainder_tp=True,  time_stop=False),
    ExitModel("I1_partial_chand2_eod", partial_r=1.0, trail_k=2.0, trail_from="partial", remainder_tp=False, time_stop=False),
    ExitModel("I2_chand2_eod",         partial_r=0.0, trail_k=2.0, trail_from="entry",   remainder_tp=False, time_stop=False),
    ExitModel("I3_partial_chand3_eod", partial_r=1.0, trail_k=3.0, trail_from="partial", remainder_tp=False, time_stop=False),
    ExitModel("I5_fixed1.5R_eod",      partial_r=0.0, trail_k=0.0, remainder_tp=True,  time_stop=False),   # tp passed as 1.5R by caller
    ExitModel("I6_partialTP_eod",      partial_r=1.0, trail_k=0.0, remainder_tp=True,  time_stop=False),   # 50% at 1R, rest to 2R, BE
    ExitModel("I4_partial_chand2_hold",partial_r=1.0, trail_k=2.0, trail_from="partial", remainder_tp=False, time_stop=False),   # NO eod flat
]

MODELS = [
    ExitModel("M0_current",            partial_r=0.0, trail_k=0.0, remainder_tp=True),
    ExitModel("M1_partial_fixedTP",    partial_r=1.0, trail_k=0.0, remainder_tp=True),
    ExitModel("M2_partial_chand3",     partial_r=1.0, trail_k=3.0, trail_from="partial", remainder_tp=False),
    ExitModel("M3_partial_chand2",     partial_r=1.0, trail_k=2.0, trail_from="partial", remainder_tp=False),
    ExitModel("M4_partial_chand4",     partial_r=1.0, trail_k=4.0, trail_from="partial", remainder_tp=False),
    ExitModel("M5_chand3_only",        partial_r=0.0, trail_k=3.0, trail_from="entry",   remainder_tp=False),
    ExitModel("M6_chand3_plusTP",      partial_r=0.0, trail_k=3.0, trail_from="entry",   remainder_tp=True),
    ExitModel("M7_partial_chand3_ent", partial_r=1.0, trail_k=3.0, trail_from="entry",   remainder_tp=False),
    ExitModel("M8_partial_chand3_noT", partial_r=1.0, trail_k=3.0, trail_from="partial", remainder_tp=False, time_stop=False),
    ExitModel("M9_partial_chand3_TP",  partial_r=1.0, trail_k=3.0, trail_from="partial", remainder_tp=True),
    ExitModel("M10_chand3_noT",        partial_r=0.0, trail_k=3.0, trail_from="entry",   remainder_tp=False, time_stop=False),
    ExitModel("M11_chand4_noT",        partial_r=0.0, trail_k=4.0, trail_from="entry",   remainder_tp=False, time_stop=False),
    ExitModel("M12_chand2_noT",        partial_r=0.0, trail_k=2.0, trail_from="entry",   remainder_tp=False, time_stop=False),
    ExitModel("M13_chand3_noT_TP",     partial_r=0.0, trail_k=3.0, trail_from="entry",   remainder_tp=True,  time_stop=False),
]


def label_event_v3(o, h, l, c, atr, time_ms, t, is_long, entry, stop0, tp, horizon_days, m: ExitModel, cost_bps=3.0, flat_at_idx=None):
    """Returns R (position-weighted, net of cost_bps per leg round trip), plus diagnostics.
    Long logic written once; shorts mirror via `sgn`."""
    n = len(c)
    risk = abs(entry - stop0)
    if risk <= 0 or t >= n - 1:
        return None
    sgn = 1.0 if is_long else -1.0
    horizon_ms = horizon_days * 86400000
    stop = stop0
    pending_be = False               # breakeven requested by a partial fill; applied at this bar's close
    size_open = 1.0
    partial_done = m.partial_r <= 0
    partial_px = entry + sgn * m.partial_r * risk
    trail_on = m.trail_k > 0 and m.trail_from == "entry"
    extreme = entry                     # highest high (long) / lowest low (short) since entry
    legs = []                           # (fraction, exit_price, reason)
    mfe = mae = 0.0
    cost_r = (entry * cost_bps / 1e4) / risk

    def path_first_is_favourable(oi, hi, li):
        high_first = abs(hi - oi) < abs(oi - li)
        return high_first if is_long else not high_first

    exit_i = None
    for i in range(t + 1, n):
        oi, hi, li, ci = o[i], h[i], l[i], c[i]
        fav = hi if is_long else li
        adv = li if is_long else hi
        mfe = max(mfe, sgn * (fav - entry) / risk)
        mae = min(mae, sgn * (adv - entry) / risk)

        # --- fills on this bar, against the stop/targets set at the previous close ---
        stop_hit = (li <= stop) if is_long else (hi >= stop)
        stop_gap = (oi <= stop) if is_long else (oi >= stop)
        tgt_active = (not partial_done) or m.remainder_tp
        tgt_px = partial_px if not partial_done else tp
        tgt_hit = tgt_active and ((hi >= tgt_px) if is_long else (li <= tgt_px))
        tgt_gap = tgt_active and ((oi >= tgt_px) if is_long else (oi <= tgt_px))

        def close_all(px, why):
            nonlocal size_open, exit_i
            legs.append((size_open, px, why)); size_open = 0.0; exit_i = i

        def fill_target():
            nonlocal size_open, partial_done, pending_be, trail_on, exit_i
            px = oi if tgt_gap else tgt_px
            if not partial_done:
                legs.append((m.partial_frac, px, "PARTIAL")); size_open -= m.partial_frac; partial_done = True
                if m.trail_k > 0 and m.trail_from == "partial":
                    trail_on = True
                if m.breakeven_after_partial:
                    pending_be = True
            else:
                close_all(px, "TP")

        if stop_gap:
            close_all(oi, "SL_GAP" if stop == stop0 else ("BE_GAP" if stop == entry else "TRAIL_GAP"))
        elif tgt_gap:
            fill_target()
        elif stop_hit and tgt_hit:
            if path_first_is_favourable(oi, hi, li):
                fill_target()
                # after a partial fills, the (old) stop could still be hit later in the same bar
                if size_open > 0 and ((li <= stop) if is_long else (hi >= stop)):
                    close_all(stop, "SL" if stop == stop0 else ("BE" if stop == entry else "TRAIL"))
            else:
                close_all(stop, "SL" if stop == stop0 else ("BE" if stop == entry else "TRAIL"))
        elif stop_hit:
            close_all(stop, "SL" if stop == stop0 else ("BE" if stop == entry else "TRAIL"))
        elif tgt_hit:
            fill_target()

        if size_open <= 0:
            break

        # --- forced flat (intraday EOD) or time stop, at this bar's close ---
        if flat_at_idx is not None and i >= flat_at_idx:
            close_all(ci, "EOD_FLAT"); break
        if m.time_stop and time_ms[i] - time_ms[t] >= horizon_ms:
            close_all(ci, "TIME"); break

        # --- close-of-bar stop management, effective next bar ---
        if pending_be:
            stop = max(stop, entry) if is_long else min(stop, entry)
            pending_be = False
        extreme = max(extreme, hi) if is_long else min(extreme, li)
        if trail_on and not np.isnan(atr[i]):
            cand = extreme - m.trail_k * atr[i] if is_long else extreme + m.trail_k * atr[i]
            stop = max(stop, cand) if is_long else min(stop, cand)

    if size_open > 0:
        legs.append((size_open, c[n - 1], "EOD")); exit_i = n - 1
    r = sum(f * sgn * (px - entry) / risk for f, px, _ in legs) - cost_r * (1 + (len(legs) - 1) * 0.5)
    final = legs[-1][2]
    return dict(R=r, reason=final, partial=any(w == "PARTIAL" for _, _, w in legs),
                bars_held=exit_i - t, mfe_R=mfe, mae_R=mae, n_legs=len(legs))
