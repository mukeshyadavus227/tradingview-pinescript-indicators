#!/usr/bin/env python3
"""
Phase 3 step 1: choose the exit model on evidence, not preference.

Every long trigger event from Phase 2 (and the deployed subset) is re-labelled
under each candidate ExitModel with the same fill rules. Selection is made on
the TRAIN half (entries before 2021-01-01) and confirmed on TEST (2021+), so
the chosen exit is not one more in-sample pick.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from engine import run_engine, PROFILES
from labels import label_event_v3, MODELS

HERE = Path(__file__).resolve().parent
DATA, OUT = HERE / "data", HERE / "out"
SPLIT = pd.Timestamp("2021-01-01")
STRATS = ["S1_MeanRev", "S2_Breakout", "S3_Momentum", "S4_MTF"]


def relabel(profile_name, chand_k_override=None):
    prof = PROFILES[profile_name]
    ev = pd.read_csv(OUT / f"events_{profile_name}.csv")
    ev = ev[ev.is_long & (ev.score > 0)].copy()
    ev["date"] = pd.to_datetime(ev.date)
    cols = {m.name: np.full(len(ev), np.nan) for m in MODELS}
    reasons = {m.name: np.empty(len(ev), dtype=object) for m in MODELS}
    bars_held = {m.name: np.full(len(ev), np.nan) for m in MODELS}
    for sym, g in ev.groupby("symbol"):
        bars = pd.read_csv(DATA / f"{sym}.csv")
        d = run_engine(bars, prof)
        o, h, l, c = (bars[k].values.astype(float) for k in "ohlc")
        atr = d.atr.values
        tm = bars.t.values.astype(np.int64) * 1000
        for idx, row in g.iterrows():
            for m in MODELS:
                r = label_event_v3(o, h, l, c, atr, tm, int(row.t_idx), True, row.entry, row.stop, row.tp, prof.time_stop_days, m)
                if r is not None:
                    cols[m.name][ev.index.get_loc(idx)] = r["R"]
                    reasons[m.name][ev.index.get_loc(idx)] = r["reason"]
                    bars_held[m.name][ev.index.get_loc(idx)] = r["bars_held"]
    for m in MODELS:
        ev[f"R_{m.name}"] = cols[m.name]
        ev[f"why_{m.name}"] = reasons[m.name]
        ev[f"bars_{m.name}"] = bars_held[m.name]
    return ev


def table(ev, mask, label):
    rows = []
    for m in MODELS:
        col = f"R_{m.name}"
        for split, sm in (("train", ev.date < SPLIT), ("test", ev.date >= SPLIT)):
            d = ev[mask & sm]
            r = d[col].dropna()
            if len(r) < 30:
                continue
            wins, losses = r[r > 0], r[r <= 0]
            rows.append(dict(model=m.name, split=split, n=len(r), meanR=r.mean(), hit=(r > 0).mean(),
                             pf=wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf,
                             sharpe=r.mean() / r.std(ddof=1), p10=r.quantile(0.1), p90=r.quantile(0.9),
                             time_share=(d[f"why_{m.name}"] == "TIME").mean(), bars=d[f"bars_{m.name}"].mean()))
    t = pd.DataFrame(rows)
    return t.pivot(index="model", columns="split", values=["n", "meanR", "hit", "pf", "sharpe", "time_share", "bars"])


def main():
    for prof in (sys.argv[1:] or ["SWING", "POSITIONAL"]):
        ev = relabel(prof)
        ev.to_csv(OUT / f"exit_events_{prof}.csv", index=False)
        L = [f"# Exit-model study — {prof}\n",
             "Train = entries before 2021-01-01, Test = 2021 onward. R net of 3 bps per leg. Pick on train, confirm on test.\n"]
        for label, mask in (("Deployed set (Phase 2 fired)", ev.fired), ("All aligned long triggers", ev.aligned),
                            ("S4 aligned score≥70", (ev.strat == "S4_MTF") & ev.aligned & (ev.score >= 70)),
                            ("S3 all triggers", ev.strat == "S3_Momentum"),
                            ("S1 trend≥18 (Phase 3 candidate)", (ev.strat == "S1_MeanRev") & (ev.c_trend >= 18))):
            t = table(ev, mask, label)
            if t.empty:
                continue
            L.append(f"## {label}\n")
            L.append("| model | n train | n test | mean R train | mean R test | hit tr | hit te | PF tr | PF te | SR tr | SR te | TIME% te | bars te | R/bar te |")
            L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
            for name, r in t.iterrows():
                g = lambda k, s: r[(k, s)] if (k, s) in r.index else np.nan
                L.append(f"| {name} | {g('n','train'):,.0f} | {g('n','test'):,.0f} | {g('meanR','train'):+.3f} | **{g('meanR','test'):+.3f}** | "
                         f"{g('hit','train'):.0%} | {g('hit','test'):.0%} | {g('pf','train'):.2f} | {g('pf','test'):.2f} | "
                         f"{g('sharpe','train'):+.3f} | {g('sharpe','test'):+.3f} | {g('time_share','test'):.0%} | {g('bars','test'):.1f} | {g('meanR','test')/max(g('bars','test'),1)*10:+.3f} |")
            L.append("")
        (OUT / f"exit_study_{prof}.md").write_text("\n".join(L))
        print("\n".join(L))


if __name__ == "__main__":
    main()
