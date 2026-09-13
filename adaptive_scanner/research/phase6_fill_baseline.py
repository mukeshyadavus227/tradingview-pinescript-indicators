#!/usr/bin/env python3
"""
Phase 6 — the deployable baseline. Every Phase 2-4 number assumed a fill at the
signal close. A daily-close webhook fills at the NEXT OPEN at best. Re-run the
deployed v3 profiles with that fill over the full 12-year history (daily bars
only: the next session's open is the fill, the full session is the path).
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from engine import PROFILES, V3_DEPLOYED, STRAT_NAMES
from simulate import simulate_symbol, EXITS_V3
from portfolio_cap import cap_run, stats
from analysis import deflated_sharpe

DATA, OUT = Path("data"), Path("out")
syms = sorted(p.stem for p in DATA.glob("*.csv"))
SPLIT = pd.Timestamp("2021-01-01")
L = ["# Phase 6 — deployable baseline: v3 filled at the next open vs at the signal close\n",
     "Same trade generation as phase3_final.md (Pine defaults, sequential per symbol, EXITS_V3, 3 bps per leg). "
     "`close` = fill at the signal close (harness convention). `next_open` = fill at the next session's open against the engine's absolute stop, "
     "which is what the webhook → server path can actually execute. Paired on identical signals.\n"]
summary = {}
for prof_name in ("SWING", "POSITIONAL"):
    prof, params = PROFILES[prof_name], V3_DEPLOYED[prof_name]
    tl = {}
    for fill in ("close", "next_open"):
        cache = OUT / f"phase6_{prof_name}_{fill}.csv"
        if cache.exists():
            tl[fill] = pd.read_csv(cache, parse_dates=["date", "exit_date"])
        else:
            rows = []
            for sym in syms:
                rows.extend(simulate_symbol(sym, pd.read_csv(DATA / f"{sym}.csv"), prof, params, EXITS_V3, fill=fill))
            tl[fill] = pd.DataFrame(rows)
            tl[fill].to_csv(cache, index=False)
    L.append(f"## {prof_name}\n")
    L.append("| cap | fill | split | trades | mean R | hit | PF | SR ann | R per year | max DD (R) |\n|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for cap in (10, 999):
        for fill in ("close", "next_open"):
            tr = cap_run(tl[fill], cap)
            for split, d in (("all", tr), ("test 2021+", tr[tr.date >= SPLIT])):
                st = stats(d)
                L.append(f"| {cap if cap < 999 else '∞'} | {fill} | {split} | {st['n']:,} | {st['meanR']:+.3f} | {st['hit']:.0%} | {st['pf']:.2f} | {st['sr_ann']:+.2f} | {st['R_yr']:+.1f} | {st['dd']:+.1f} |")
                summary[f"{prof_name}/{fill}/cap{cap}/{split}"] = {k: v for k, v in st.items() if k != "mix"}
    # paired difference on identical signals (uncapped)
    a = tl["close"].set_index(["symbol", "date"]); b = tl["next_open"].set_index(["symbol", "date"])
    j = a.join(b, lsuffix="_c", rsuffix="_o", how="inner").reset_index()
    d = (j.R_o - j.R_c).values
    rng = np.random.default_rng(0); bs = np.array([rng.choice(d, len(d)).mean() for _ in range(4000)])
    L.append("")
    L.append(f"**Paired next_open − close, uncapped, n = {len(d):,}: {d.mean():+.3f} R per trade, 95% CI [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]; "
             f"test 2021+: {(j[j.date >= SPLIT].R_o - j[j.date >= SPLIT].R_c).mean():+.3f}.**\n")
    L.append("| strategy | n | mean R close | mean R next_open | Δ |\n|---|---:|---:|---:|---:|")
    for k, name in STRAT_NAMES.items():
        jj = j[j.k_c == k]
        if len(jj) == 0: continue
        L.append(f"| {name} | {len(jj):,} | {jj.R_c.mean():+.3f} | {jj.R_o.mean():+.3f} | {(jj.R_o - jj.R_c).mean():+.3f} |")
    summary[f"{prof_name}/paired_delta"] = float(d.mean())
    m = cap_run(tl["next_open"], 10).copy(); m["month"] = m.date.dt.to_period("M")
    mo = m.groupby("month").R.sum().values
    L.append("")
    L.append(f"**DSR, {prof_name} next_open at cap 10 (monthly units):**\n\n| N trials | DSR | MinTRL (months) |\n|---:|---:|---:|")
    for N in (100, 500, 2000):
        sr, sr0, dsr, mintrl = deflated_sharpe(mo, n_trials=N, sr_var=0.015)
        L.append(f"| {N} | **{dsr:.3f}** | {mintrl:,.0f} |")
        summary[f"{prof_name}/next_open/dsr/N{N}"] = dsr
    L.append("")
(OUT / "phase6_fill_baseline.md").write_text("\n".join(L))
json.dump(summary, open(OUT / "phase6_fill_summary.json", "w"), indent=1, default=str)
print("\n".join(L))
