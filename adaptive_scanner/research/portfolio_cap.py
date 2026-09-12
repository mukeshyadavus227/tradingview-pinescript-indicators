#!/usr/bin/env python3
"""
Slot-capped portfolio pass over the per-symbol sequential trade lists.
Admits a candidate only if open positions < cap; same-day candidates are
ordered by strategy priority (S1 > S4 > S3 > S2), then score. Rejected trades
are dropped (approximation: the symbol would actually be free for a later
signal, so this is a mild lower bound on v3 density).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "out"
PRIO = {1: 0, 4: 1, 3: 2, 2: 3}
SPLIT = pd.Timestamp("2021-01-01")


def cap_run(tr, cap):
    tr = tr.copy()
    tr["date"] = pd.to_datetime(tr.date); tr["exit_date"] = pd.to_datetime(tr.exit_date)
    tr["prio"] = tr.k.map(PRIO)
    tr = tr.sort_values(["date", "prio", "score"], ascending=[True, True, False])
    open_exits, taken = [], []
    for _, x in tr.iterrows():
        open_exits = [e for e in open_exits if e >= x.date]
        if len(open_exits) < cap:
            open_exits.append(x.exit_date); taken.append(True)
        else:
            taken.append(False)
    return tr[np.array(taken)]


def stats(tr):
    r = tr.R.values
    m = tr.copy(); m["month"] = m.date.dt.to_period("M")
    mo = m.groupby("month").R.sum()
    yrs = (tr.date.max() - tr.date.min()).days / 365.25
    return dict(n=len(tr), meanR=r.mean(), hit=(r > 0).mean(), pf=r[r > 0].sum() / -r[r <= 0].sum(),
                sr_ann=mo.mean() / mo.std(ddof=1) * np.sqrt(12), R_yr=r.sum() / yrs, worst=mo.min(),
                dd=(mo.cumsum() - mo.cumsum().cummax()).min(), mix={k: int(v) for k, v in tr.strat.value_counts().items()})


L = ["# Slot-capped portfolio comparison\n",
     "Same per-symbol trade lists as phase3_simulation.md, admitted through a concurrent-position cap with priority S1 > S4 > S3. R net of costs.\n"]
for prof in ("SWING", "POSITIONAL"):
    L.append(f"## {prof}\n")
    L.append("| cap | system | trades | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for cap in (5, 10, 20, 999):
        for ver, fn in (("v2", f"sim_{prof}_v2.csv"), ("v3", f"sim_{prof}_v3.csv")):
            tr = cap_run(pd.read_csv(OUT / fn), cap)
            for split, d in (("all", tr), ("test", tr[tr.date >= SPLIT])):
                s = stats(d)
                L.append(f"| {cap if cap < 999 else '∞'} | {ver} {split} | {s['n']:,} | {s['meanR']:+.3f} | {s['hit']:.0%} | {s['pf']:.2f} | "
                         f"{s['sr_ann']:+.2f} | {s['R_yr']:+.1f} | {s['worst']:+.1f} | {s['dd']:+.1f} | {s['mix']} |")
    L.append("")
(OUT / "phase3_slot_cap.md").write_text("\n".join(L))
print("\n".join(L))
