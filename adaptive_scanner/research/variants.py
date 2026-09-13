#!/usr/bin/env python3
"""Rule variants under realistic slot caps. Decides the POSITIONAL configuration."""
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd
from engine import PROFILES, DEFAULT_PARAMS, V3_PARAMS
from simulate import simulate_symbol, EXITS_V2, EXITS_V3
from portfolio_cap import cap_run, stats

DATA, OUT = Path("data"), Path("out")
syms = sorted(p.stem for p in DATA.glob("*.csv"))
SPLIT = pd.Timestamp("2021-01-01")

VARIANTS = {
    "v2":                    (DEFAULT_PARAMS, EXITS_V2),
    "v3":                    (V3_PARAMS, EXITS_V3),
    "v3 noS1":               (replace(V3_PARAMS, s1_enabled=False), EXITS_V3),
    "v3 noS1 S3thr":         (replace(V3_PARAMS, s1_enabled=False, s3_useThreshold=True), EXITS_V3),
    "v3 noS1 S4only":        (replace(V3_PARAMS, s1_enabled=False, priority=(4,)), EXITS_V3),
    "v3 S3thr":              (replace(V3_PARAMS, s3_useThreshold=True), EXITS_V3),
    "v2rules v3exits":       (DEFAULT_PARAMS, EXITS_V3),
}
L = ["# Rule variants under slot caps (test period 2021+, R net of costs)\n"]
for prof_name, names in (("POSITIONAL", ["v2", "v3", "v3 noS1", "v3 noS1 S3thr", "v3 noS1 S4only", "v2rules v3exits"]),
                         ("SWING", ["v2", "v3", "v3 S3thr", "v2rules v3exits"])):
    prof = PROFILES[prof_name]
    L.append(f"## {prof_name}\n")
    L.append("| cap | variant | trades | mean R | hit | PF | SR ann | R per year | max DD (R) | mix |\n|---:|---|---:|---:|---:|---:|---:|---:|---:|---|")
    trades = {}
    for nm in names:
        params, exits = VARIANTS[nm]
        rows = []
        for sym in syms:
            rows.extend(simulate_symbol(sym, pd.read_csv(DATA / f"{sym}.csv"), prof, params, exits))
        trades[nm] = pd.DataFrame(rows)
    for cap in (5, 10, 20):
        for nm in names:
            tr = cap_run(trades[nm], cap); te = tr[tr.date >= SPLIT]
            s = stats(te)
            L.append(f"| {cap} | {nm} | {s['n']:,} | {s['meanR']:+.3f} | {s['hit']:.0%} | {s['pf']:.2f} | {s['sr_ann']:+.2f} | {s['R_yr']:+.1f} | {s['dd']:+.1f} | {s['mix']} |")
    L.append("")
(OUT / "phase3_variants.md").write_text("\n".join(L))
print("\n".join(L))
