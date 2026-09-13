#!/usr/bin/env python3
"""
Phase 5 validation for the INTRADAY_15M profile. Same shape as Phases 2-3:
every trigger event labelled under every exit model, eligible subset = what
would deploy, train/test split, then sequential + slot-capped simulation.

Data ceiling: ~5,000 x 15m bars per symbol ≈ 9 months (one regime). Enough to
kill; not enough to bless. Train = sessions before args.split, test = after.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine_intraday import run_intraday, DEFAULT, STRAT_NAMES_I
from labels import label_event_v3, INTRADAY_MODELS
from server.allocator import Allocator, AllocatorConfig, Candidate, OpenPosition

HERE = Path(__file__).resolve().parent
D15, DD, OUT = HERE / "data_15m", HERE / "data", HERE / "out"
SPLIT = "2026-06-15"
COST_HEADLINE = 5.0
M = {m.name: m for m in INTRADAY_MODELS}


def load15(sym):
    p = D15 / f"{sym}.csv.gz"
    if not p.exists():
        p = D15 / f"{sym}.csv"
    return pd.read_csv(p)


def build_events(syms):
    spy = load15("SPY")
    rows = []
    frames = {}
    for sym in syms:
        b15, bd = load15(sym), pd.read_csv(DD / f"{sym}.csv")
        d = run_intraday(b15, bd, spy)
        frames[sym] = (b15, d)
        o, h, l, c = (b15[k].values.astype(float) for k in "ohlc")
        atr, tm = d.atr.values, b15.t.values.astype(np.int64) * 1000
        for k, trig_col, elig_col, stop_col in ((5, "s5_trig", "s5_elig", "s5_stopD"), (6, "s6_trig", "s6_elig", "s6_stopD"), (3, "s3_trig", "s3_elig", "s3_stopD")):
            idx = np.where(d[trig_col].values & d.warm.values & d.liquidity.values & (d.bars_left.values >= 3))[0]
            for t in idx:
                entry = round(c[t], 2); stop = round(c[t] - d[stop_col].values[t], 2); risk = entry - stop
                if risk <= 0:
                    continue
                row = dict(symbol=sym, t_idx=int(t), date=d.date.values[t], slot=int(d.slot.values[t]), k=k, strat=STRAT_NAMES_I[k],
                           eligible=bool(d[elig_col].values[t]), deployed=bool(d.eligible.values[t] and d.best.values[t] == k),
                           entry=entry, stop=stop, risk=risk, rvol_tod=float(d.rvol_tod.values[t]), rvol_cum=float(d.rvol_cum.values[t]),
                           gap_atr=float(d.gap_atr.values[t]), or_width_atr=float(d.or_width_atr.values[t]), rs_sess=float(d.rs_sess.values[t]),
                           rs_20=float(d.rs_20.values[t]), trend_up=bool(d.trend_up.values[t]), trend_strong=bool(d.trend_strong.values[t]),
                           dRoc20=float(d.dRoc20.values[t]), stop_pct=float(risk / entry * 100))
                eod = int(d.eod_idx.values[t])
                for m in INTRADAY_MODELS:
                    tp = entry + (1.5 if m.name.startswith("I5") else 2.0) * risk
                    flat = None if m.name.startswith("I4") else eod
                    for bps in (0, 2, 5, 10):
                        r = label_event_v3(o, h, l, c, atr, tm, int(t), True, entry, stop, tp, 30, m, cost_bps=bps, flat_at_idx=flat)
                        if r is None:
                            continue
                        row[f"R_{m.name}_{bps}"] = r["R"]
                        if bps == COST_HEADLINE:
                            row[f"why_{m.name}"] = r["reason"]; row[f"bars_{m.name}"] = r["bars_held"]; row[f"mfe_{m.name}"] = r["mfe_R"]
                rows.append(row)
    return pd.DataFrame(rows), frames


def summ(r):
    r = r.dropna()
    if len(r) < 20:
        return None
    w, lo = r[r > 0], r[r <= 0]
    return dict(n=len(r), mean=r.mean(), hit=(r > 0).mean(), pf=w.sum() / -lo.sum() if lo.sum() < 0 else np.inf, sr=r.mean() / r.std(ddof=1))


def row(label, s):
    return f"| {label} | {s['n']:,} | {s['mean']:+.3f} | {s['hit']:.0%} | {s['pf']:.2f} | {s['sr']:+.3f} |" if s else f"| {label} | <20 | | | | |"


HDR = "| population | n | mean R | hit | PF | SR/trade |\n|---|---:|---:|---:|---:|---:|"


def main():
    syms = sorted(p.stem.replace(".csv", "") for p in D15.glob("*.csv*"))
    ev, frames = build_events(syms)
    ev.to_csv(OUT / "events_INTRADAY.csv", index=False)
    tr, te = ev[ev.date < SPLIT], ev[ev.date >= SPLIT]
    base = f"R_I0_fixed2R_eod_{int(COST_HEADLINE)}"
    L = [f"# Phase 5 — INTRADAY_15M validation\n",
         f"{len(syms)} symbols, 15m RTH bars {ev.date.min()} → {ev.date.max()}; train < {SPLIT} ≤ test. R net of {COST_HEADLINE:.0f} bps round trip unless stated. "
         f"Trigger events: {len(ev):,}. **One regime only** — this can kill a strategy, not bless one.\n"]
    # 1. per strategy, baseline exit
    L.append("## 1. Trigger vs eligible vs deployed, baseline exit (fixed 2R, EOD flat)\n")
    L.append(HDR)
    for k, name in STRAT_NAMES_I.items():
        for split, d in (("train", tr), ("test", te)):
            dk = d[d.k == k]
            L.append(row(f"{name} · all triggers · {split}", summ(dk[base])))
            L.append(row(f"{name} · eligible · {split}", summ(dk[dk.eligible][base])))
            L.append(row(f"{name} · deployed · {split}", summ(dk[dk.deployed][base])))
    L.append("")
    # 2. cost curve on eligible
    L.append("## 2. Cost sensitivity (eligible, all periods, baseline exit)\n")
    L.append("| strategy | 0 bps | 2 bps | 5 bps | 10 bps |\n|---|---:|---:|---:|---:|")
    for k, name in STRAT_NAMES_I.items():
        d = ev[(ev.k == k) & ev.eligible]
        L.append(f"| {name} | " + " | ".join(f"{d[f'R_I0_fixed2R_eod_{b}'].mean():+.3f}" for b in (0, 2, 5, 10)) + " |")
    L.append("")
    # 3. exit models on eligible
    L.append("## 3. Exit models (eligible events)\n")
    L.append("| model | n train | n test | mean R train | mean R test | hit te | PF te | SR te | EOD% te | bars te |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, name in STRAT_NAMES_I.items():
        L.append(f"| **{name}** | | | | | | | | | |")
        for m in INTRADAY_MODELS:
            col = f"R_{m.name}_{int(COST_HEADLINE)}"
            a = summ(tr[(tr.k == k) & tr.eligible][col]); b = summ(te[(te.k == k) & te.eligible][col])
            if not a or not b:
                continue
            tt = te[(te.k == k) & te.eligible]
            L.append(f"| {m.name} | {a['n']:,} | {b['n']:,} | {a['mean']:+.3f} | **{b['mean']:+.3f}** | {b['hit']:.0%} | {b['pf']:.2f} | {b['sr']:+.3f} | "
                     f"{(tt[f'why_{m.name}'] == 'EOD_FLAT').mean():.0%} | {tt[f'bars_{m.name}'].mean():.1f} |")
    L.append("")
    # 4. conditioning: slot, gap, rvol, RS
    L.append("## 4. What conditions outcome? (all triggers, baseline exit, all periods)\n")
    for k, name in STRAT_NAMES_I.items():
        d = ev[ev.k == k].copy()
        if len(d) < 100:
            continue
        L.append(f"**{name}**\n")
        L.append("| condition | bucket | n | mean R | hit |\n|---|---|---:|---:|---:|")
        d["slot_b"] = pd.cut(d.slot, [-1, 3, 7, 12, 18, 25], labels=["09:30-10:15", "10:30-11:15", "11:30-12:30", "12:45-14:00", "14:15-15:45"])
        d["gap_b"] = pd.cut(d.gap_atr, [-99, -0.5, -0.1, 0.1, 0.5, 99], labels=["gap<-0.5ATR", "-0.5..-0.1", "flat", "+0.1..+0.5", "gap>+0.5ATR"])
        d["rv_b"] = pd.cut(d.rvol_cum, [0, 0.8, 1.2, 1.8, 3, 99], labels=["<0.8", "0.8-1.2", "1.2-1.8", "1.8-3", ">3"])
        d["rs_b"] = np.where(d.rs_sess > 0, "RS>0 vs SPY", "RS≤0")
        d["tr_b"] = np.where(d.trend_strong, "50>200 & above", np.where(d.trend_up, "above 200 only", "below 200"))
        for cond, col in (("time of entry", "slot_b"), ("gap at open", "gap_b"), ("cum ToD rvol", "rv_b"), ("session RS", "rs_b"), ("daily trend", "tr_b")):
            g = d.groupby(col, observed=True)[base].agg(["size", "mean", lambda x: (x > 0).mean()])
            for b_, r_ in g.iterrows():
                if r_["size"] >= 30:
                    L.append(f"| {cond} | {b_} | {int(r_['size']):,} | {r_['mean']:+.3f} | {r_.iloc[2]:.0%} |")
        L.append("")
    (OUT / "phase5_intraday.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
