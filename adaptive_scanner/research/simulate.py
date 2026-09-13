#!/usr/bin/env python3
"""
Sequential single-position simulation per symbol — the honest view of a
scanner that holds one position per chart — with per-strategy exit models.
Compares the Phase-2 engine (v2 rules, M0 exits) against Phase 3 (v3 rules,
validated exits) on identical data, then reports portfolio-level statistics.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from engine import run_engine, PROFILES, DEFAULT_PARAMS, V3_PARAMS, STRAT_NAMES
from labels import label_event_v3, MODELS

HERE = Path(__file__).resolve().parent
DATA, OUT = HERE / "data", HERE / "out"
M = {m.name: m for m in MODELS}
EXITS_V2 = {1: M["M0_current"], 2: M["M0_current"], 3: M["M0_current"], 4: M["M0_current"]}
EXITS_V3 = {1: M["M5_chand3_only"], 2: M["M0_current"], 3: M["M8_partial_chand3_noT"], 4: M["M8_partial_chand3_noT"]}
SPLIT = pd.Timestamp("2021-01-01")


def simulate_symbol(sym, bars, profile, params, exits, fill="close", mintick=None):
    """fill="close": entry at the signal close (harness convention, not executable live).
    fill="next_open": entry at the next session's open against the engine's absolute stop — the
    fill a daily-close webhook can actually get (Phase 6).
    mintick: forwarded to the labeller (tick-rounded chandelier, as the Pine); parity_test passes it."""
    d = run_engine(bars, profile, params)
    o, h, l, c = (bars[k].values.astype(float) for k in "ohlc")
    atr, tm = d.atr.values, bars.t.values.astype(np.int64) * 1000
    trades, busy_until = [], -1
    cd_ms, last = profile.cooldown_min * 60000, 0
    for t in np.where(d.eligible.values)[0]:
        if t <= busy_until or (last and tm[t] - last < cd_ms):
            continue
        k = int(d.bestStrat.values[t])
        entry, stop, tp = float(d.entryRef.values[t]), float(d.stopPrice.values[t]), float(d.tpPrice.values[t])
        if fill == "next_open":
            if t + 1 >= len(c):
                continue
            entry = round(float(o[t + 1]), 2)
            if entry <= stop:
                continue
        lab = label_event_v3(o, h, l, c, atr, tm, int(t), True, entry, stop, tp, profile.time_stop_days, exits[k], mintick=mintick)
        if lab is None:
            continue
        busy_until = t + lab["bars_held"]; last = tm[t]
        trades.append(dict(symbol=sym, k=k, strat=STRAT_NAMES[k], date=pd.Timestamp(d.date.values[t]),
                           exit_date=pd.Timestamp(d.date.values[min(len(d) - 1, t + lab["bars_held"])]),
                           score=float(d.bestScore.values[t]), regime=int(d.regime.values[t]), R=lab["R"],
                           reason=lab["reason"], bars=lab["bars_held"], mfe=lab["mfe_R"], mae=lab["mae_R"],
                           dMom121=float(d.dMom121.values[t]), distFromHi=float(d.distFromHi.values[t]),
                           rvPctile=float(d.rvPctile.values[t]), dAtrPct=float(d.dAtrPct.values[t]),
                           dRoc20=float(d.dRoc20.values[t]), dRoc60=float(d.dRoc60.values[t]),
                           # parity fields (parity_test.py): prices and bars the Strategy Tester export is compared against
                           entry=entry, stop0=stop, exit_px=lab["exit_price"],
                           partial_date=(pd.Timestamp(d.date.values[lab["partial_idx"]]) if lab["partial_idx"] is not None else pd.NaT),
                           partial_px=lab["partial_px"],
                           poc_date=(pd.Timestamp(d.date.values[lab["poc_bar"]]) if lab["poc_bar"] is not None else pd.NaT),
                           poc_px=lab["poc_px"]))
    return trades


def portfolio_stats(tr, label):
    tr = tr.sort_values("date")
    yrs = (tr.date.max() - tr.date.min()).days / 365.25
    r = tr.R.values
    # concurrency: positions open per day
    days = pd.date_range(tr.date.min(), tr.exit_date.max(), freq="B")
    conc = np.zeros(len(days))
    idx = {d: i for i, d in enumerate(days)}
    for _, x in tr.iterrows():
        a, b = idx.get(x.date, None), idx.get(x.exit_date, None)
        if a is not None and b is not None:
            conc[a:b + 1] += 1
    m = tr.copy(); m["month"] = m.date.dt.to_period("M")
    monthly = m.groupby("month").R.sum()
    sr_m = monthly.mean() / monthly.std(ddof=1)
    return dict(label=label, n=len(tr), per_sym_yr=len(tr) / tr.symbol.nunique() / yrs, meanR=r.mean(), hit=(r > 0).mean(),
                pf=r[r > 0].sum() / -r[r <= 0].sum(), sr_trade=r.mean() / r.std(ddof=1), sr_month=sr_m,
                sr_month_ann=sr_m * np.sqrt(12), bars=tr.bars.mean(), conc_mean=conc.mean(), conc_p95=np.percentile(conc, 95),
                conc_max=conc.max(), R_per_yr_per_sym=r.sum() / tr.symbol.nunique() / yrs,
                worst_month=monthly.min(), dd=(monthly.cumsum() - monthly.cumsum().cummax()).min())


def fmt(d):
    return (f"| {d['label']} | {d['n']:,} | {d['per_sym_yr']:.2f} | {d['meanR']:+.3f} | {d['hit']:.0%} | {d['pf']:.2f} | "
            f"{d['sr_trade']:+.3f} | {d['sr_month']:+.3f} | {d['sr_month_ann']:+.2f} | {d['bars']:.1f} | {d['conc_mean']:.1f} / {d['conc_p95']:.0f} / {d['conc_max']:.0f} | "
            f"{d['R_per_yr_per_sym']:+.2f} | {d['worst_month']:+.1f} | {d['dd']:+.1f} |")


HDR = ("| system | trades | /sym-yr | mean R | hit | PF | SR/trade | SR/month | SR ann | bars | open pos mean/p95/max | R per sym-yr | worst mo | max DD (R) |\n"
       "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|---:|---:|---:|")


def main():
    syms = sorted(p.stem for p in DATA.glob("*.csv"))
    L = ["# Phase 3 — sequential simulation, v2 vs v3\n",
         "One position per symbol at a time; cooldown applies; R net of 3 bps per leg. 48 symbols. "
         "Test = entries 2021+. v2 = Phase-2 rules with the fixed-target exit (M0). v3 = S1 trend-gated (no regime gate), "
         "S2 removed, S3 on trigger, S4 ≥ 75, priority S1 > S4 > S3, exits S1:M5 / S3,S4:M8.\n"]
    results = {}
    for prof_name in (sys.argv[1:] or ["SWING", "POSITIONAL"]):
        prof = PROFILES[prof_name]
        for ver, params, exits in (("v2", DEFAULT_PARAMS, EXITS_V2), ("v3", V3_PARAMS, EXITS_V3),
                                   ("v3 rules + M0 exits", V3_PARAMS, EXITS_V2), ("v2 rules + v3 exits", DEFAULT_PARAMS, EXITS_V3)):
            rows = []
            for sym in syms:
                rows.extend(simulate_symbol(sym, pd.read_csv(DATA / f"{sym}.csv"), prof, params, exits))
            tr = pd.DataFrame(rows)
            tr.to_csv(OUT / f"sim_{prof_name}_{ver.replace(' ', '_').replace('+', 'plus')}.csv", index=False)
            results[(prof_name, ver)] = tr
        L.append(f"## {prof_name}\n")
        L.append(HDR)
        for ver in ("v2", "v3 rules + M0 exits", "v2 rules + v3 exits", "v3"):
            tr = results[(prof_name, ver)]
            L.append(fmt(portfolio_stats(tr, f"{ver} — all")))
            L.append(fmt(portfolio_stats(tr[tr.date >= SPLIT], f"{ver} — test 2021+")))
        L.append("")
        tr = results[(prof_name, "v3")]
        L.append(f"**v3 by strategy ({prof_name}):**\n")
        L.append("| strategy | trades | mean R all | mean R test | hit | PF | bars | exit reasons (test) |\n|---|---:|---:|---:|---:|---:|---:|---|")
        for k, name in STRAT_NAMES.items():
            d = tr[tr.k == k]
            if len(d) == 0:
                continue
            te = d[d.date >= SPLIT]
            r = d.R.values
            L.append(f"| {name} | {len(d):,} | {r.mean():+.3f} | {te.R.mean():+.3f} | {(r>0).mean():.0%} | {r[r>0].sum()/-r[r<=0].sum():.2f} | {d.bars.mean():.1f} | {te.reason.value_counts(normalize=True).round(2).to_dict()} |")
        L.append("")
        # What should the server rank S3 candidates on?
        s3 = tr[tr.k == 3]
        L.append(f"**S3 cross-sectional feature check ({prof_name}, v3 S3 trades, Spearman vs R):**\n")
        L.append("| feature | ρ | p |\n|---|---:|---:|")
        for f in ("score", "dMom121", "dRoc20", "dRoc60", "distFromHi", "rvPctile", "dAtrPct"):
            x = s3[f].replace([np.inf, -np.inf], np.nan)
            ok = x.notna()
            rho, pv = stats.spearmanr(x[ok], s3.R[ok])
            L.append(f"| {f} | {rho:+.3f} | {pv:.2g} |")
        L.append("")
    (OUT / "phase3_simulation.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
