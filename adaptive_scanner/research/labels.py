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
