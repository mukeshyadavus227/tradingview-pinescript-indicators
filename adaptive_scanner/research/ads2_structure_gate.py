#!/usr/bin/env python3
"""
ADS2 v2.3.0 — swing structure gate, OFF vs ON, on the existing validation harness.

Gate (as implemented in ads2_daily_scanner.pine, input "Require close > SMA200"):
an S3 MOM or S4 MTF swing deploy additionally needs close > SMA200 AND
GR Trend Template >= min (default 3). S1 MR is never gated.

Trade generation is the deployed SWING profile exactly as phase6_fill_baseline.py runs
it (engine.V3_DEPLOYED["SWING"], simulate.EXITS_V3, sequential one position per symbol,
next-open fill against the absolute stop, 3 bps per leg). The gate only removes
eligibility (simulate_symbol's `post` hook), so OFF must reproduce phase6_fill_baseline.md.

What this harness is NOT: it mirrors ASR v3 SWING, the rule set ADS2's swing lane was
built from. ADS2 differs in its 10-bar cooldown (harness: 5 days), its earnings blackout
(none here) and current-bar SMA200 for S1's trend component (harness: prior bar). The
universe is the 48-symbol research set (large caps + ETFs), not a screener universe.

Outputs: out/ads2_structure_gate.md, out/ads2_structure_gate.json
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import engine
import pine_ta as ta
import simulate
from analysis import deflated_sharpe
from portfolio_cap import cap_run, stats

HERE = Path(__file__).resolve().parent
DATA, OUT = HERE / "data", HERE / "out"
SPLIT = pd.Timestamp("2021-01-01")
PROF = engine.PROFILES["SWING"]
PARAMS = engine.V3_DEPLOYED["SWING"]
CAP = 10
TT_GRID = (0, 1, 2, 3, 4, 5)          # 0 = "close > SMA200" alone
RNG = np.random.default_rng(20261106)


# ── ADS2 structure, current bar (mirrors the Pine: tt_stack … tt_weekly, aboveLT) ──────────
def structure(bars):
    o, h, l, c = (bars[k].values.astype(float) for k in "ohlc")
    sma50, sma150, sma200 = ta.sma(c, 50), ta.sma(c, 150), ta.sma(c, 200)
    hi52, lo52 = ta.highest(h, 252), ta.lowest(l, 252)
    dates_et = pd.to_datetime(bars.t.values, unit="s", utc=True).tz_convert(engine.ET)
    wk = engine.weekly_context(dates_et, o, h, l, c, PARAMS.s4_wkFast, PARAMS.s4_wkSlow)
    wkF, wkS, wkC = wk["s4_wkF"], wk["s4_wkS"], wk["s4_wkC"]
    with np.errstate(invalid="ignore", divide="ignore"):
        stack = ~np.isnan(sma150) & (c > sma50) & (sma50 > sma150) & (sma150 > sma200)
        s200_21 = ta.shift(sma200, 21)
        rising = ~np.isnan(s200_21) & (sma200 > s200_21)
        pct_lo = np.where(lo52 > 0, (c / lo52 - 1.0) * 100.0, np.nan)
        pct_hi = np.where(hi52 > 0, (c / hi52 - 1.0) * 100.0, np.nan)
        off_low = ta.nz(pct_lo, 0.0) >= 25.0
        near_hi = ta.nz(pct_hi, -100.0) >= -25.0
        weekly = ~np.isnan(wkF) & ~np.isnan(wkS) & (wkF > wkS) & (wkC > wkF)
        above200 = ~np.isnan(sma200) & (c > sma200)
    tt = stack.astype(int) + rising.astype(int) + off_low.astype(int) + near_hi.astype(int) + weekly.astype(int)
    return tt, above200


def make_gate(scope, min_tt):
    def post(d, bars):
        tt, above = structure(bars)
        blocked = np.isin(d.bestStrat.values, scope) & ~(above & (tt >= min_tt))
        d = d.copy()
        d["eligible"] = d.eligible.values & ~blocked
        return d
    return post


VARIANTS = {"OFF": None, "ON S3 only tt3": make_gate((3,), 3)}
for k in TT_GRID:
    VARIANTS[f"ON S3+S4 tt{k}"] = make_gate((3, 4), k)
IMPL = "ON S3+S4 tt3"                  # the variant the Pine implements at its defaults


def work(sym):
    bars = pd.read_csv(DATA / f"{sym}.csv")
    d0 = engine.run_engine(bars, PROF, PARAMS)
    # One engine pass per symbol: every variant reuses the frame (gates only mask eligibility).
    simulate.run_engine = lambda _b, _p, _q: d0
    out = {name: simulate.simulate_symbol(sym, bars, PROF, PARAMS, simulate.EXITS_V3, fill="next_open", post=post)
           for name, post in VARIANTS.items()}
    tt, above = structure(bars)
    flags = pd.DataFrame({"symbol": sym, "date": pd.to_datetime(d0.date.values), "tt": tt, "above200": above})
    return out, flags


def monthly(tr):
    m = tr.copy(); m["month"] = m.date.dt.to_period("M")
    return m.groupby("month").R.sum()


def row(name, d):
    if len(d) < 2:
        return f"| {name} | {len(d)} | | | | | | |"
    s = stats(d)
    return (f"| {name} | {s['n']:,} | {s['hit']:.0%} | {s['meanR']:+.3f} | {s['pf']:.2f} | {s['sr_ann']:+.2f} | "
            f"{s['R_yr']:+.1f} | {s['dd']:+.1f} |")


def main():
    syms = sorted(p.stem for p in DATA.glob("*.csv"))
    trades = {n: [] for n in VARIANTS}; flags = []
    with ProcessPoolExecutor(max_workers=2) as ex:
        for out, fl in ex.map(work, syms):
            for n in VARIANTS:
                trades[n].extend(out[n])
            flags.append(fl)
    T = {n: pd.DataFrame(v) for n, v in trades.items()}
    for n in T:
        T[n]["date"] = pd.to_datetime(T[n].date); T[n]["exit_date"] = pd.to_datetime(T[n].exit_date)
    C = {n: cap_run(T[n], CAP) for n in T}
    F = pd.concat(flags)
    summary = {}
    L = ["# ADS2 v2.3.0 — swing structure gate, OFF vs ON\n",
         "Deployed SWING profile (ASR v3 mirror: S1 > S4 > S3, EXITS_V3), 48 symbols, daily bars "
         f"{T['OFF'].date.min():%Y-%m-%d} → {T['OFF'].exit_date.max():%Y-%m-%d}, sequential one position per symbol, "
         "fill at the next open against the absolute stop, R net of 3 bps per leg. "
         f"Gate = close > SMA200 AND GR Trend Template ≥ k on S3/S4 signals (S1 never gated). "
         f"Pine default = `{IMPL}`. Portfolio = slot cap {CAP}, priority S1 > S4 > S3.\n"]

    # Regression: OFF must equal phase6_fill_baseline.md (SWING next_open)
    base = json.load(open(OUT / "phase6_fill_summary.json"))
    b = base.get(f"SWING/next_open/cap{CAP}/all", {})
    s_off = stats(C["OFF"])
    reg = (b.get("n") == s_off["n"]) and abs(b.get("meanR", 9) - s_off["meanR"]) < 1e-9
    summary["regression_vs_phase6"] = {"phase6": {k: b.get(k) for k in ("n", "meanR")}, "OFF": {"n": s_off["n"], "meanR": s_off["meanR"]}, "match": bool(reg)}
    L.append(f"**Regression check:** OFF at cap {CAP} = {s_off['n']:,} trades, {s_off['meanR']:+.3f} R; "
             f"phase6_fill_baseline = {b.get('n', 'n/a')} trades, {b.get('meanR', float('nan')):+.3f} R → "
             f"{'IDENTICAL' if reg else 'MISMATCH — harness changed, results below are not comparable'}.\n")

    hdr = "| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |\n|---|---:|---:|---:|---:|---:|---:|---:|"
    for title, pick in ((f"Portfolio, cap {CAP}", C), ("Uncapped, sequential per symbol", T)):
        L.append(f"## {title}\n")
        for split, f in (("all", lambda d: d), ("2015–2020 (pre-split)", lambda d: d[d.date < SPLIT]), ("2021+ (harness test window)", lambda d: d[d.date >= SPLIT])):
            L.append(f"**{split}**\n"); L.append(hdr)
            for n in ["OFF", IMPL, "ON S3 only tt3"] + [v for v in VARIANTS if v.startswith("ON S3+S4") and v != IMPL]:
                d = f(pick[n]); L.append(row(n, d))
                if len(d) > 1:
                    summary[f"{title}/{split}/{n}"] = {k: v for k, v in stats(d).items() if k != "mix"}
            L.append("")

    # Removed trades: which OFF trades does the default gate take out, and what were they worth?
    off = T["OFF"].merge(F, on=["symbol", "date"], how="left")
    gate_ok = off.above200 & (off.tt >= 3)
    rem = off[off.k.isin([3, 4]) & ~gate_ok]; kept = off[~(off.k.isin([3, 4]) & ~gate_ok)]
    def ci(x):
        if len(x) < 5: return (np.nan, np.nan)
        bs = [RNG.choice(x, len(x)).mean() for _ in range(4000)]
        return np.percentile(bs, 2.5), np.percentile(bs, 97.5)
    L.append("## What the default gate removes (OFF trade list, uncapped)\n")
    L.append("| group | trades | win rate | avg R | 95% CI avg R |\n|---|---:|---:|---:|---|")
    for nm, d in (("removed (S3/S4 failing the gate)", rem), ("kept", kept), ("removed S3", rem[rem.k == 3]), ("removed S4", rem[rem.k == 4])):
        if len(d):
            lo, hi = ci(d.R.values)
            L.append(f"| {nm} | {len(d):,} | {(d.R > 0).mean():.0%} | {d.R.mean():+.3f} | [{lo:+.3f}, {hi:+.3f}] |")
            summary[f"removed/{nm}"] = {"n": int(len(d)), "meanR": float(d.R.mean()), "ci": [float(lo), float(hi)]}
    diff = rem.R.mean() - kept.R.mean()
    bs = [RNG.choice(rem.R.values, len(rem)).mean() - RNG.choice(kept.R.values, len(kept)).mean() for _ in range(4000)]
    L.append(f"\nRemoved − kept: {diff:+.3f} R per trade, 95% CI [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}].\n")
    summary["removed_minus_kept"] = {"d": float(diff), "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}

    # Walk-forward: each calendar year, pick the config (OFF or ON S3+S4 tt0..5) with the best
    # annualised monthly Sharpe at cap 10 on ALL prior years (expanding), apply it to that year.
    cands = ["OFF"] + [f"ON S3+S4 tt{k}" for k in TT_GRID]
    mo = {n: monthly(C[n]) for n in cands}
    years = sorted({p.year for p in mo["OFF"].index})
    L.append("## Walk-forward (expanding window, yearly re-selection, cap 10)\n")
    L.append("Each test year uses the configuration whose monthly Sharpe was best on every earlier year. "
             "Candidates: OFF and the gate at k = 0…5. First test year needs three years of history.\n")
    L.append("| test year | chosen | OOS R (chosen) | OOS R (OFF) | OOS R (default gate) |\n|---|---|---:|---:|---:|")
    wf_ch, wf_off, wf_imp = [], [], []
    for y in years[3:]:
        best, best_sr = None, -np.inf
        for n in cands:
            tr = mo[n][[p.year < y for p in mo[n].index]]
            if len(tr) > 12 and tr.std(ddof=1) > 0:
                sr = tr.mean() / tr.std(ddof=1)
                if sr > best_sr: best, best_sr = n, sr
        te = {n: mo[n][[p.year == y for p in mo[n].index]] for n in (best, "OFF", IMPL)}
        wf_ch.append(te[best]); wf_off.append(te["OFF"]); wf_imp.append(te[IMPL])
        L.append(f"| {y} | {best} | {te[best].sum():+.1f} | {te['OFF'].sum():+.1f} | {te[IMPL].sum():+.1f} |")
    def wf_line(name, parts):
        s = pd.concat(parts); cum = s.cumsum()
        return (f"| {name} | {s.sum():+.1f} | {s.mean() / s.std(ddof=1) * np.sqrt(12):+.2f} | {(cum - cum.cummax()).min():+.1f} |"), s
    L.append("\n| stitched OOS | total R | SR ann | max DD (R) |\n|---|---:|---:|---:|")
    for name, parts in (("walk-forward choice", wf_ch), ("OFF", wf_off), (f"default gate ({IMPL})", wf_imp)):
        line, s = wf_line(name, parts); L.append(line)
        summary[f"wf/{name}"] = {"total_R": float(s.sum()), "sr_ann": float(s.mean() / s.std(ddof=1) * np.sqrt(12))}
    # Paired monthly difference, default gate − OFF, over the whole window
    a, b2 = monthly(C[IMPL]), monthly(C["OFF"])
    j = pd.concat([a.rename("on"), b2.rename("off")], axis=1).fillna(0.0)
    dm = (j.on - j.off).values
    bsm = [RNG.choice(dm, len(dm)).mean() for _ in range(4000)]
    L.append(f"\nPaired monthly R, default gate − OFF (cap 10, {len(dm)} months): {dm.mean():+.2f} R/month, "
             f"95% CI [{np.percentile(bsm, 2.5):+.2f}, {np.percentile(bsm, 97.5):+.2f}].\n")
    summary["paired_monthly_on_minus_off"] = {"mean": float(dm.mean()), "ci": [float(np.percentile(bsm, 2.5)), float(np.percentile(bsm, 97.5))]}

    # Deflated Sharpe (monthly units), honest trial count as in the README (N = 500)
    L.append("## Deflated Sharpe, cap 10, monthly units\n\n| variant | SR (monthly) | DSR N=100 | DSR N=500 |\n|---|---:|---:|---:|")
    for n in ("OFF", IMPL):
        m = monthly(C[n]).values
        sr, _, d100, _ = deflated_sharpe(m, n_trials=100, sr_var=0.015)
        _, _, d500, _ = deflated_sharpe(m, n_trials=500, sr_var=0.015)
        L.append(f"| {n} | {sr:+.3f} | {d100:.3f} | {d500:.3f} |")
        summary[f"dsr/{n}"] = {"sr_m": sr, "N100": d100, "N500": d500}
    L.append("")
    (OUT / "ads2_structure_gate.md").write_text("\n".join(L))
    json.dump(summary, open(OUT / "ads2_structure_gate.json", "w"), indent=1, default=float)
    print("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
