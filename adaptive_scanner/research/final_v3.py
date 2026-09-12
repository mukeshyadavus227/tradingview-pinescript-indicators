#!/usr/bin/env python3
"""Deployed v3 (Pine defaults) vs v2, per-symbol sequential + slot caps. Produces the Phase 3 headline table."""
from pathlib import Path
import json, numpy as np, pandas as pd
from engine import PROFILES, DEFAULT_PARAMS, V3_DEPLOYED, STRAT_NAMES
from simulate import simulate_symbol, EXITS_V2, EXITS_V3, portfolio_stats
from portfolio_cap import cap_run, stats
from analysis import deflated_sharpe

DATA, OUT = Path("data"), Path("out")
syms = sorted(p.stem for p in DATA.glob("*.csv"))
SPLIT = pd.Timestamp("2021-01-01")
L = ["# Phase 3 — deployed v3 vs v2 (Pine defaults)\n",
     "Per-symbol sequential (one position per chart), then a portfolio slot cap with priority S1 > S4 > S3. R net of 3 bps per leg. Test = entries 2021+.\n"]
summary = {}
for prof_name in ("SWING", "POSITIONAL"):
    prof = PROFILES[prof_name]
    tl = {}
    for ver, params, exits in (("v2", DEFAULT_PARAMS, EXITS_V2), ("v3", V3_DEPLOYED[prof_name], EXITS_V3)):
        rows = []
        for sym in syms:
            rows.extend(simulate_symbol(sym, pd.read_csv(DATA / f"{sym}.csv"), prof, params, exits))
        tl[ver] = pd.DataFrame(rows)
        tl[ver].to_csv(OUT / f"final_{prof_name}_{ver}.csv", index=False)
    L.append(f"## {prof_name}\n")
    L.append("| cap | system | trades | /sym-yr | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for cap in (5, 10, 20, 999):
        for ver in ("v2", "v3"):
            tr = cap_run(tl[ver], cap)
            for split, d in (("all", tr), ("test", tr[tr.date >= SPLIT])):
                st = stats(d); yrs = (d.date.max() - d.date.min()).days / 365.25
                L.append(f"| {cap if cap < 999 else '∞'} | {ver} {split} | {st['n']:,} | {st['n']/48/yrs:.2f} | {st['meanR']:+.3f} | {st['hit']:.0%} | {st['pf']:.2f} | "
                         f"{st['sr_ann']:+.2f} | {st['R_yr']:+.1f} | {st['worst']:+.1f} | {st['dd']:+.1f} | {st['mix']} |")
                if cap == 10:
                    summary[f"{prof_name}/{ver}/{split}/cap10"] = {k: (v if not isinstance(v, dict) else v) for k, v in st.items()}
    L.append("")
    tr = tl["v3"]
    L.append(f"**v3 {prof_name} by strategy (uncapped):**\n")
    L.append("| strategy | trades | mean R | test R | hit | PF | bars | test exit reasons |\n|---|---:|---:|---:|---:|---:|---:|---|")
    for k, name in STRAT_NAMES.items():
        d = tr[tr.k == k]
        if len(d) == 0: continue
        te = d[d.date >= SPLIT]; r = d.R.values
        L.append(f"| {name} | {len(d):,} | {r.mean():+.3f} | {te.R.mean():+.3f} | {(r>0).mean():.0%} | {r[r>0].sum()/-r[r<=0].sum():.2f} | {d.bars.mean():.1f} | {te.reason.value_counts(normalize=True).round(2).to_dict()} |")
    # DSR on the cap-10 monthly series, N = 14 exit models x 7 rule variants ~ 100, and 500
    tr10 = cap_run(tl["v3"], 10); m = tr10.copy(); m["month"] = m.date.dt.to_period("M")
    mo = m.groupby("month").R.sum().values
    L.append("")
    L.append(f"**DSR, v3 {prof_name} at cap 10 (monthly units; selection searched ~14 exit models × 7 rule variants):**\n")
    L.append("| N trials | E[max SR] | DSR | MinTRL (months) |\n|---:|---:|---:|---:|")
    for N in (100, 500, 2000):
        sr, sr0, dsr, mintrl = deflated_sharpe(mo, n_trials=N, sr_var=0.015)
        L.append(f"| {N} | {sr0:+.3f} | **{dsr:.3f}** | {mintrl:,.0f} |")
        summary[f"{prof_name}/dsr/N{N}"] = dsr
    L.append("")
(OUT / "phase3_final.md").write_text("\n".join(L))
json.dump(summary, open(OUT / "phase3_summary.json", "w"), indent=1, default=str)
print("\n".join(L))
