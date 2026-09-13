#!/usr/bin/env python3
"""
Phase 6 — intraday triggers as ENTRY TIMING for the validated SWING profile.

The daily engine decides WHAT to buy (signal at the close of day D, with its own
stop / target geometry). This study asks WHEN to fill on day D+1 (or later), and
whether a 15m trigger beats the two fills a daily-close signal can actually get
in the live pipeline: market-on-open next day, or market-on-close next day.

Entry rules (all long; the daily engine's stop and target are kept as ABSOLUTE
prices, which is what the server places against the fill):

  E0 close_D       fill at the signal close (the Phase-3 harness convention;
                   NOT executable live — the webhook cannot fill at 16:00)
  E1 open_D1       market-on-open next session
  E2 close_D1      market-on-close next session
  E3 orb           first 15m close above the 30-minute opening-range high,
                   10:00-12:30, within W sessions; else no trade
  E4 vwap_conf     first 15m close (>= 10:00) above session VWAP AND above the
                   signal close, within W sessions; else no trade
  E5 limit_close   resting limit at the signal close on D+1 (fills at the open
                   if the open is below it, else on touch); else no trade
  E6 limit_atr     resting limit at signal close - 0.25 x daily ATR; else no trade
  E7 limit_or_moc  E5, falling back to market-on-close D+1 if unfilled

Path after the fill: the fill session's remaining 15m bars are collapsed into a
partial daily bar (o = fill, h/l from the bars AFTER a close-fill, or from the
fill bar onward for a touch-fill), then the validated daily exit engine
(labels.label_event_v3 with EXITS_V3) runs on daily bars exactly as in Phase 3.

Sample: the intraday history is 193 sessions (2025-12-04 .. 2026-09-11), so
this is a PAIRED comparison on the same signals, not a walk-forward.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from engine import run_engine, PROFILES, V3_SWING, STRAT_NAMES
from engine_intraday import run_intraday, DEFAULT as IP
from labels import label_event_v3
from simulate import EXITS_V3

HERE = Path(__file__).resolve().parent
DATA, D15, OUT = HERE / "data", HERE / "data_15m", HERE / "out"
COST_BPS = 3.0
RULES = ["close_D", "open_D1", "close_D1", "orb", "vwap_conf", "limit_close", "limit_atr", "limit_or_moc"]


def load15(sym):
    p = D15 / f"{sym}.csv.gz"
    return pd.read_csv(p if p.exists() else D15 / f"{sym}.csv")


def daily_signals(sym, bars, prof, params, exits, sequential=True):
    """Signal bars of the deployed SWING profile. sequential=True reproduces simulate_symbol's
    one-position-per-chart set (what deploys); False = every eligible bar."""
    d = run_engine(bars, prof, params)
    o, h, l, c = (bars[k].values.astype(float) for k in "ohlc")
    atr, tm = d.atr.values, bars.t.values.astype(np.int64) * 1000
    out, busy_until, last = [], -1, 0
    cd_ms = prof.cooldown_min * 60000
    for t in np.where(d.eligible.values)[0]:
        if sequential and (t <= busy_until or (last and tm[t] - last < cd_ms)):
            continue
        k = int(d.bestStrat.values[t])
        entry, stop, tp = float(d.entryRef.values[t]), float(d.stopPrice.values[t]), float(d.tpPrice.values[t])
        lab = label_event_v3(o, h, l, c, atr, tm, int(t), True, entry, stop, tp, prof.time_stop_days, exits[k])
        if lab is None:
            continue
        busy_until = t + lab["bars_held"]; last = tm[t]
        out.append(dict(symbol=sym, t=int(t), k=k, strat=STRAT_NAMES[k], date=str(d.date.values[t]),
                        entry0=entry, stop0=stop, tp0=tp, dAtr=float(atr[t]), score=float(d.bestScore.values[t]),
                        R_close_D=lab["R"], reason_close_D=lab["reason"], bars_close_D=lab["bars_held"]))
    return d, out


def session_rows(i15, date):
    idx = i15.get(date)
    return None if idx is None else idx


def find_fill(rule, sess, b15, x, p=IP, window=1):
    """Return (day_offset j, fill_bar s, fill_px, post_from) or None.
    post_from = first 15m bar index (within the session) whose h/l count as post-fill path."""
    o, h, l, c = (b15[k].values for k in "ohlc")
    vwap, or_hi, slot = b15.vwap.values, b15.or_hi.values, b15.slot.values
    entry0, dAtr = x["entry0"], x["dAtr"]
    for j in range(1, window + 1):
        rows = sess[j - 1] if j - 1 < len(sess) else None
        if rows is None or len(rows) < 20:      # no / short session -> cannot fill this day
            continue
        r0 = rows[0]
        if rule == "open_D1":
            return j, 0, float(o[r0]), 0
        if rule == "close_D1":
            return j, len(rows) - 1, float(c[rows[-1]]), len(rows)
        if rule == "orb":
            for s, i in enumerate(rows):
                if p.or_bars <= slot[i] <= p.orb_last_slot and not np.isnan(or_hi[i]) and c[i] > or_hi[i]:
                    return j, s, float(c[i]), s + 1
        elif rule == "vwap_conf":
            for s, i in enumerate(rows):
                if slot[i] >= p.or_bars and slot[i] <= p.last_entry_slot and not np.isnan(vwap[i]) and c[i] > vwap[i] and c[i] > entry0:
                    return j, s, float(c[i]), s + 1
        elif rule in ("limit_close", "limit_atr", "limit_or_moc"):
            level = entry0 if rule != "limit_atr" else entry0 - 0.25 * dAtr
            if o[r0] <= level:
                return j, 0, float(o[r0]), 0
            for s, i in enumerate(rows):
                if l[i] <= level:
                    return j, s, float(level), s          # touch fill: the fill bar's low counts as post-fill path
            if rule == "limit_or_moc":
                return j, len(rows) - 1, float(c[rows[-1]]), len(rows)
        if rule in ("open_D1", "close_D1", "limit_close", "limit_atr", "limit_or_moc"):
            return None                                  # single-session rules
    return None


def label_with_fill(x, fill, dd, b15, sess, prof, exits, cost_bps=COST_BPS, anchor="signal"):
    """Run the daily exit engine from an intraday fill. anchor='signal' keeps the engine's absolute
    stop; 'fill' re-anchors the same stop distance to the fill price."""
    j, s, px, post_from = fill
    t = x["t"]
    o, h, l, c = (dd[k].values.astype(float).copy() for k in "ohlc")
    atr, tm = dd.atr.values, dd.t.values.astype(np.int64) * 1000
    ti = t + j
    if ti >= len(c):
        return None
    rows = sess[j - 1]
    post = rows[post_from:]
    ho, hh, hl, hc = (b15[k].values for k in "ohlc")
    if len(post) > 0:
        o[ti] = px; h[ti] = float(np.max(hh[post])); l[ti] = float(np.min(hl[post])); c[ti] = float(hc[post[-1]])
        t_eff = ti - 1
    else:
        t_eff = ti                                       # fill at the last bar: path starts next session
    stop = x["stop0"] if anchor == "signal" else px - (x["entry0"] - x["stop0"])
    tp = x["tp0"] if anchor == "signal" else px + (x["tp0"] - x["entry0"])
    if px <= stop:
        return dict(R=np.nan, reason="FILL_BELOW_STOP", bars_held=0, risk_ratio=np.nan)
    lab = label_event_v3(o, h, l, c, atr, tm, t_eff, True, px, stop, tp, prof.time_stop_days, exits[x["k"]], cost_bps=cost_bps)
    if lab is None:
        return None
    lab["risk_ratio"] = (px - stop) / (x["entry0"] - x["stop0"])
    lab["slip_atr"] = (px - x["entry0"]) / x["dAtr"]
    lab["fill_day"] = j; lab["fill_slot"] = int(b15.slot.values[rows[min(s, len(rows) - 1)]])
    return lab


def run(prof_name="SWING", window=3, anchor="signal", sequential=True, cost_bps=COST_BPS):
    prof, params, exits = PROFILES[prof_name], V3_SWING, EXITS_V3
    syms = sorted(p.stem for p in DATA.glob("*.csv"))
    spy15 = load15("SPY")
    recs = []
    for sym in syms:
        bars = pd.read_csv(DATA / f"{sym}.csv")
        raw15 = load15(sym)
        dd, sigs = daily_signals(sym, bars, prof, params, exits, sequential)
        b15 = run_intraday(raw15, bars, spy15, IP)
        i15 = {d: np.where(b15.date.values == d)[0] for d in pd.unique(b15.date.values)}
        first15, last15 = min(i15), max(i15)
        ddates = [str(v) for v in dd.date.values]
        for x in sigs:
            t = x["t"]
            if not (first15 < x["date"] < last15) or t + window >= len(ddates):
                continue
            sess = [i15.get(ddates[t + j]) for j in range(1, window + 1)]
            if sess[0] is None:
                continue
            rec = dict(x)
            for rule in RULES:
                if rule == "close_D":
                    rec["R_close_D"] = x["R_close_D"]; rec["filled_close_D"] = True; rec["slip_close_D"] = 0.0; rec["rr_close_D"] = 1.0
                    continue
                w = window if rule in ("orb", "vwap_conf") else 1
                f = find_fill(rule, sess, b15, x, IP, w)
                lab = label_with_fill(x, f, dd, b15, sess, prof, exits, cost_bps, anchor) if f else None
                rec[f"filled_{rule}"] = bool(lab) and not np.isnan(lab["R"])
                rec[f"R_{rule}"] = lab["R"] if lab else np.nan
                rec[f"reason_{rule}"] = lab["reason"] if lab else ("NO_FILL" if f is None else "NA")
                rec[f"slip_{rule}"] = lab["slip_atr"] if lab and "slip_atr" in lab else np.nan
                rec[f"rr_{rule}"] = lab["risk_ratio"] if lab else np.nan
                rec[f"day_{rule}"] = lab["fill_day"] if lab and "fill_day" in lab else np.nan
            recs.append(rec)
    return pd.DataFrame(recs)


def paired(df, a, b, n_boot=4000, seed=0):
    m = df[f"filled_{a}"] & df[f"filled_{b}"]
    d = (df.loc[m, f"R_{a}"] - df.loc[m, f"R_{b}"]).values
    if len(d) < 5:
        return len(d), np.nan, (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    bs = np.array([rng.choice(d, len(d)).mean() for _ in range(n_boot)])
    return len(d), d.mean(), (np.percentile(bs, 2.5), np.percentile(bs, 97.5))


def table(df, title):
    L = [f"### {title}\n",
         "| rule | signals | filled | fill % | mean R (filled) | mean R per signal | hit | PF | median slip (ATR) | risk vs signal | Δ vs open_D1 (paired, 95% CI) | Δ vs close_D (paired) |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    n = len(df)
    for rule in RULES:
        f = df[f"filled_{rule}"].values.astype(bool); r = df.loc[f, f"R_{rule}"].values
        if f.sum() == 0:
            L.append(f"| {rule} | {n} | 0 | 0% | | | | | | | | |"); continue
        pf = r[r > 0].sum() / -r[r <= 0].sum() if (r <= 0).any() and (r > 0).any() else np.nan
        k1, d1, ci1 = paired(df, rule, "open_D1"); k0, d0, ci0 = paired(df, rule, "close_D")
        L.append(f"| {rule} | {n} | {f.sum()} | {f.mean():.0%} | {r.mean():+.3f} | {np.nansum(df[f'R_{rule}'].values) / n:+.3f} | {(r > 0).mean():.0%} | {pf:.2f} | "
                 f"{np.nanmedian(df.loc[f, f'slip_{rule}']):+.2f} | {np.nanmean(df.loc[f, f'rr_{rule}']):.2f} | "
                 f"{d1:+.3f} [{ci1[0]:+.2f}, {ci1[1]:+.2f}] n={k1} | {d0:+.3f} [{ci0[0]:+.2f}, {ci0[1]:+.2f}] |")
    return L


def main():
    L = ["# Phase 6 — entry timing for the SWING profile (daily signal, intraday fill)\n",
         "Daily v3 SWING signals (Pine defaults, sequential one-position-per-chart, EXITS_V3), each re-filled under every entry rule. "
         "R is measured against the engine's ABSOLUTE stop unless stated. Net of 3 bps per leg. "
         "Intraday history: 193 RTH sessions, 2025-12-04 .. 2026-09-11, 48 symbols. Paired comparison on identical signals; the sample is one regime, not a walk-forward.\n"]
    summary = {}
    df = run(sequential=True, anchor="signal")
    df.to_csv(OUT / "phase6_entry_timing.csv", index=False)
    L += table(df, f"Sequential signal set, stop anchored at the signal (n = {len(df)})")
    summary["n_sequential"] = int(len(df))
    for rule in RULES:
        f = df[f"filled_{rule}"].astype(bool)
        summary[f"{rule}/meanR"] = float(df.loc[f, f"R_{rule}"].mean()) if f.any() else None
        summary[f"{rule}/perSignal"] = float(np.nansum(df[f"R_{rule}"].values) / len(df))
        summary[f"{rule}/fill"] = float(f.mean())
    L.append("")
    L.append("**By strategy (mean R of filled, sequential set):**\n")
    L.append("| strategy | n | " + " | ".join(RULES) + " |\n|---|---:|" + "---:|" * len(RULES))
    for k, name in STRAT_NAMES.items():
        d = df[df.k == k]
        if len(d) == 0: continue
        cells = []
        for rule in RULES:
            f = d[f"filled_{rule}"].astype(bool)
            cells.append(f"{d.loc[f, f'R_{rule}'].mean():+.2f} ({f.sum()})" if f.any() else "—")
        L.append(f"| {name} | {len(d)} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("**What the trigger rules skip:** mean R the skipped signals would have earned at the next open.\n")
    L.append("| rule | skipped | mean R at open_D1 of skipped | hit | mean R at open_D1 of taken |\n|---|---:|---:|---:|---:|")
    for rule in ("orb", "vwap_conf", "limit_close", "limit_atr"):
        sk = ~df[f"filled_{rule}"].astype(bool) & df["filled_open_D1"].astype(bool)
        tk = df[f"filled_{rule}"].astype(bool) & df["filled_open_D1"].astype(bool)
        L.append(f"| {rule} | {sk.sum()} | {df.loc[sk, 'R_open_D1'].mean():+.3f} | {(df.loc[sk, 'R_open_D1'] > 0).mean():.0%} | {df.loc[tk, 'R_open_D1'].mean():+.3f} |")
    L.append("")
    df2 = run(sequential=True, anchor="fill")
    L += table(df2, f"Robustness: same signals, stop re-anchored to the fill (n = {len(df2)})")
    L.append("")
    df3 = run(sequential=False, anchor="signal")
    df3.to_csv(OUT / "phase6_entry_timing_all.csv", index=False)
    L += table(df3, f"Robustness: every eligible signal bar, overlapping (n = {len(df3)})")
    L.append("")
    L.append("**Cost sensitivity (sequential set, mean R per signal, unfilled = 0):**\n")
    L.append("| bps per leg | " + " | ".join(RULES) + " |\n|---:|" + "---:|" * len(RULES))
    for bps in (3.0, 5.0, 10.0):
        dfc = df if bps == 3.0 else run(sequential=True, anchor="signal", cost_bps=bps)
        L.append(f"| {bps:.0f} | " + " | ".join(f"{np.nansum(dfc[f'R_{r}'].values) / len(dfc):+.3f}" for r in RULES) + " |")
    (OUT / "phase6_entry_timing.md").write_text("\n".join(L))
    json.dump(summary, open(OUT / "phase6_summary.json", "w"), indent=1)
    print("\n".join(L))


if __name__ == "__main__":
    main()
