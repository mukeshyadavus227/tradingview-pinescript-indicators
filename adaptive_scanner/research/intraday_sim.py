#!/usr/bin/env python3
"""
Phase 5 — sequential and slot-capped simulation of the INTRADAY_15M profile,
in % NAV, with the same allocator the server runs. Exit model and risk per
trade are parameters; the study script decides which exit to use.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine_intraday import run_intraday, DEFAULT, STRAT_NAMES_I
from labels import label_event_v3, INTRADAY_MODELS
from server.allocator import Allocator, AllocatorConfig, Candidate, OpenPosition
from portfolio_sim import metrics, fmt, HDR

HERE = Path(__file__).resolve().parent
D15, DD, OUT = HERE / "data_15m", HERE / "data", HERE / "out"
M = {m.name: m for m in INTRADAY_MODELS}
KEYS = {5: "S5-I", 6: "S6-I", 3: "S3-I"}


def load15(sym):
    p = D15 / f"{sym}.csv.gz"
    return pd.read_csv(p if p.exists() else D15 / f"{sym}.csv")


def sequential(sym, d, b15, model, cost_bps, cooldown_bars=3, max_per_day=3, priority=(5, 6, 3)):
    o, h, l, c = (b15[k].values.astype(float) for k in "ohlc")
    atr, tm = d.atr.values, b15.t.values.astype(np.int64) * 1000
    trades, busy_until, last_t, per_day = [], -1, -10 ** 9, {}
    elig = {5: d.s5_elig.values, 6: d.s6_elig.values, 3: d.s3_elig.values}
    stopD = {5: d.s5_stopD.values, 6: d.s6_stopD.values, 3: d.s3_stopD.values}
    for t in np.where(d.warm.values & d.liquidity.values & (d.slot.values <= DEFAULT.last_entry_slot) & (d.bars_left.values >= 3))[0]:
        k = next((kk for kk in priority if elig[kk][t]), 0)
        if k == 0 or t <= busy_until or t - last_t < cooldown_bars or per_day.get(d.date.values[t], 0) >= max_per_day:
            continue
        entry = round(c[t], 2); stop = round(c[t] - stopD[k][t], 2); risk = entry - stop
        if risk <= 0:
            continue
        flat = None if model.name.startswith("I4") else int(d.eod_idx.values[t])
        lab = label_event_v3(o, h, l, c, atr, tm, int(t), True, entry, stop, entry + 2 * risk, 30, model, cost_bps=cost_bps, flat_at_idx=flat)
        if lab is None:
            continue
        busy_until = t + lab["bars_held"]; last_t = t; per_day[d.date.values[t]] = per_day.get(d.date.values[t], 0) + 1
        ex = min(len(d) - 1, t + lab["bars_held"])
        trades.append(dict(symbol=sym, k=k, key=KEYS[k], strat=STRAT_NAMES_I[k], profile="INTRADAY",
                           date=pd.Timestamp(d.date.values[t]), exit_date=pd.Timestamp(d.date.values[ex]),
                           t_idx=int(t), score=float(d.rvol_cum.values[t]) if not np.isnan(d.rvol_cum.values[t]) else 0.0,
                           R=lab["R"], reason=lab["reason"], bars=lab["bars_held"]))
    return trades


def portfolio(tr, cap, risk_pct, start_equity=100_000.0):
    """Intraday positions open and close inside a session; admission is per bar, equity marks daily at exit."""
    alloc = Allocator(AllocatorConfig(max_positions=cap, risk_pct=risk_pct, max_heat_pct=cap * risk_pct, one_per_symbol=True, rule="fifo"))
    d = tr.sort_values(["t_idx_abs"]).copy()
    open_pos = []  # (exit_abs, OpenPosition, R)
    equity = start_equity
    taken = {}
    eq_curve, heat_curve = {}, {}
    for _, x in d.iterrows():
        # settle positions whose exit bar has passed
        for e in [e for e in open_pos if e[0] <= x.t_idx_abs]:
            equity += e[2] * e[1].risk_dollars; open_pos.remove(e)
        dec = alloc.admit(Candidate(x.symbol, "INTRADAY", x.key, x.score, str(_)), [e[1] for e in open_pos], equity)
        taken[_] = dec.admit
        if dec.admit:
            open_pos.append((x.t_idx_abs + x.bars, OpenPosition(x.symbol, "INTRADAY", x.key, dec.risk_dollars), float(x.R)))
        eq_curve[x.date] = equity; heat_curve[x.date] = sum(e[1].risk_dollars for e in open_pos) / equity
    for e in open_pos:
        equity += e[2] * e[1].risk_dollars
    eq = pd.Series(eq_curve).sort_index()
    eq.attrs["heat"] = pd.Series(heat_curve).sort_index()
    return eq, d[[taken.get(i, False) for i in d.index]]


def main(model_name="I0_fixed2R_eod", cost_bps=5.0):
    syms = sorted(p.stem.replace(".csv", "") for p in D15.glob("*.csv*"))
    spy = load15("SPY")
    model = M[model_name]
    rows = []
    for sym in syms:
        b15, bd = load15(sym), pd.read_csv(DD / f"{sym}.csv")
        d = run_intraday(b15, bd, spy)
        tr = sequential(sym, d, b15, model, cost_bps)
        # absolute bar index across symbols: use timestamp order (all symbols share the RTH grid)
        for x in tr:
            x["t_idx_abs"] = int(b15.t.values[x["t_idx"]])
        rows.extend(tr)
    tr = pd.DataFrame(rows)
    tr.to_csv(OUT / f"intraday_trades_{model_name}.csv", index=False)
    L = [f"# Phase 5 — intraday sequential + slot-capped simulation ({model_name}, {cost_bps:.0f} bps)\n"]
    yrs = (tr.date.max() - tr.date.min()).days / 365.25
    L.append(f"{len(syms)} symbols, {tr.date.min().date()} → {tr.date.max().date()} ({yrs:.2f} years — ONE regime). "
             f"Sequential per symbol: one position at a time, 45-min cooldown, ≤3 entries/day.\n")
    L.append("| strategy | trades | /sym-day | mean R | hit | PF | SR/trade | bars | exit reasons |\n|---|---:|---:|---:|---:|---:|---:|---:|---|")
    days = tr.date.nunique()
    for k, name in STRAT_NAMES_I.items():
        dk = tr[tr.k == k]
        if len(dk) == 0:
            continue
        r = dk.R.values
        L.append(f"| {name} | {len(dk):,} | {len(dk)/len(syms)/days:.2f} | {r.mean():+.3f} | {(r>0).mean():.0%} | {r[r>0].sum()/-r[r<=0].sum():.2f} | {r.mean()/r.std(ddof=1):+.3f} | {dk.bars.mean():.1f} | {dk.reason.value_counts(normalize=True).round(2).to_dict()} |")
    r = tr.R.values
    L.append(f"| **ALL** | {len(tr):,} | {len(tr)/len(syms)/days:.2f} | {r.mean():+.3f} | {(r>0).mean():.0%} | {r[r>0].sum()/-r[r<=0].sum():.2f} | {r.mean()/r.std(ddof=1):+.3f} | {tr.bars.mean():.1f} | |")
    L.append("")
    L.append("## Slot-capped portfolio (one position per symbol, FIFO). Annualised figures extrapolate 9 months — read the sign and the ranking, not the level.\n")
    L.append(HDR)
    for risk in (0.5, 1.0):
        for cap in (5, 10, 20):
            eq, taken = portfolio(tr, cap, risk)
            L.append(fmt(metrics(eq, taken, f"cap {cap} · risk {risk}%")))
    (OUT / f"phase5_sim_{model_name}.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["I0_fixed2R_eod"]), *([float(sys.argv[2])] if len(sys.argv) > 2 else []))
