#!/usr/bin/env python3
"""
Phase 4 — cross-profile portfolio simulation in % NAV.

SWING v3 and POSITIONAL v3 candidates from the same 48 symbols compete for a
shared risk budget. Positions are sized as a fixed fraction of CURRENT equity
at risk (R units → % NAV), so results are in the terms the account experiences:
CAGR, volatility, Sharpe, max drawdown, heat.

Admission rules compared:
  fifo        first come, no priority (baseline)
  priority    validated per-trade expectancy: S1 > S4-POS > S4-SWING > S3
  per_bar     expectancy per bar held: S1 > S4-SWING ≈ S3 > S4-POS
  reserve     half the slots reserved per profile, priority within
Symbol uniqueness (one open position per symbol across profiles) on/off.
"""
import sys, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.allocator import Allocator, AllocatorConfig, Candidate, OpenPosition   # the SAME admission code the server runs

OUT = Path(__file__).resolve().parent / "out"
SPLIT = pd.Timestamp("2021-01-01")
KEY = {("SWING", 1): "S1-SW", ("SWING", 3): "S3-SW", ("SWING", 4): "S4-SW", ("POSITIONAL", 4): "S4-POS"}
PRIORITY = {"S1-SW": 0, "S4-POS": 1, "S4-SW": 2, "S3-SW": 3}
PER_BAR = {"S1-SW": 0, "S4-SW": 1, "S3-SW": 2, "S4-POS": 3}


def load():
    sw = pd.read_csv(OUT / "final_SWING_v3.csv"); sw["profile"] = "SWING"
    po = pd.read_csv(OUT / "final_POSITIONAL_v3.csv"); po["profile"] = "POSITIONAL"
    df = pd.concat([sw, po], ignore_index=True)
    df["date"] = pd.to_datetime(df.date); df["exit_date"] = pd.to_datetime(df.exit_date)
    df["key"] = [KEY[(p, k)] for p, k in zip(df.profile, df.k)]
    return df


def run(df, cap, rule, unique_symbol, risk_pct, start_equity=100_000.0):
    """Event-driven: candidates by date; admission by server.allocator; equity compounds at exit."""
    alloc = Allocator(AllocatorConfig(max_positions=cap, risk_pct=risk_pct, max_heat_pct=cap * risk_pct, one_per_symbol=unique_symbol, rule=rule))
    d = df.sort_values(["date", "score"], ascending=[True, False])
    open_pos = []            # (exit_date, OpenPosition, R)
    equity = start_equity
    taken = {}
    eq_curve, heat_curve = {}, {}
    days = pd.date_range(d.date.min(), d.exit_date.max(), freq="B")
    di = 0

    def settle(upto):
        nonlocal equity, di
        while di < len(days) and days[di] <= upto:
            for e in [e for e in open_pos if e[0] <= days[di]]:
                equity += e[2] * e[1].risk_dollars
                open_pos.remove(e)
            eq_curve[days[di]] = equity
            heat_curve[days[di]] = sum(e[1].risk_dollars for e in open_pos) / equity
            di += 1

    for date, g in d.groupby("date", sort=True):
        settle(date)
        cands = [Candidate(r.symbol, r.profile, r.key, float(r.score), str(i)) for i, r in g.iterrows()]
        decisions = alloc.admit_batch(cands, [e[1] for e in open_pos], equity)
        rows = {str(i): r for i, r in g.iterrows()}
        for dec in decisions:
            taken[int(dec.candidate.signal_id)] = dec.admit
            if dec.admit:
                r = rows[dec.candidate.signal_id]
                open_pos.append((r.exit_date, OpenPosition(r.symbol, r.profile, r.key, dec.risk_dollars), float(r.R)))
    settle(days[-1])
    eq = pd.Series(eq_curve).sort_index()
    eq.attrs["heat"] = pd.Series(heat_curve).sort_index()
    tr = d[[taken.get(i, False) for i in d.index]]
    return eq, tr


def metrics(eq, tr, label):
    rets = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    vol = rets.std() * np.sqrt(252)
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else np.nan
    ddser = eq / eq.cummax() - 1
    dd = ddser.min()
    heat = eq.attrs.get("heat", pd.Series(0.0, index=eq.index))
    heat_at_trough = float(heat.loc[ddser.idxmin()]) if len(heat) else 0.0
    dd_bound = dd - heat_at_trough          # every open position stopped out at the trough
    mo = eq.resample("ME").last().pct_change().dropna()
    return dict(label=label, cagr=cagr, vol=vol, sharpe=sharpe, maxdd=dd, dd_bound=dd_bound, heat_mean=float(heat.mean()), heat_max=float(heat.max()),
                worst_month=mo.min(), calmar=cagr / -dd if dd < 0 else np.nan,
                trades_yr=len(tr) / yrs, mix={k: int(v) for k, v in tr.key.value_counts().items()})


def fmt(m):
    return (f"| {m['label']} | {m['cagr']:+.1%} | {m['vol']:.1%} | {m['sharpe']:+.2f} | {m['maxdd']:+.1%} | {m['dd_bound']:+.1%} | "
            f"{m['heat_mean']:.1%} / {m['heat_max']:.0%} | {m['worst_month']:+.1%} | {m['calmar']:.2f} | {m['trades_yr']:.0f} | {m['mix']} |")


HDR = ("| config | CAGR | vol | Sharpe | DD (closed) | DD bound | heat mean/max | worst month | Calmar | trades/yr | mix |\n"
       "|---|---:|---:|---:|---:|---:|:---:|---:|---:|---:|---|")


def main():
    df = load()
    test = df[df.date >= SPLIT]
    L = ["# Phase 4 — cross-profile portfolio in % NAV\n",
         "SWING v3 + POSITIONAL v3 candidates (48 symbols) compete for a shared slot budget. Each admitted trade risks `risk %` of current equity; "
         "P&L booked at exit (mark-at-cost between), so `DD (closed)` ignores open losses; `DD bound` assumes every open position is stopped at the trough — the truth lies between. "
         "Test = entries 2021+ only (a 5.7-year window). Survivor-universe caveat applies to every level here; use the tables for the RANKING of rules, not for return expectations.\n"]
    summary = {}
    for period, data in (("test 2021+", test), ("all 2015+", df)):
        L.append(f"## {period}\n")
        for risk in (1.0, 1.5):
            L.append(f"### risk {risk:.1f}% of equity per trade\n")
            L.append(HDR)
            for cap in (5, 8, 10, 15, 20):
                for rule in ("fifo", "priority", "per_bar", "reserve"):
                    for uniq in (True, False):
                        eq, tr = run(data, cap, rule, uniq, risk)
                        m = metrics(eq, tr, f"cap {cap} · {rule} · {'1/sym' if uniq else 'multi'}")
                        L.append(fmt(m))
                        summary[f"{period}|{risk}|{cap}|{rule}|{uniq}"] = {k: v for k, v in m.items() if k != "mix"}
            L.append("")
        # single-profile references at cap 10
        L.append(f"### references, risk 1.0%, cap 10 (single profile)\n")
        L.append(HDR)
        for prof in ("SWING", "POSITIONAL"):
            eq, tr = run(data[data.profile == prof], 10, "priority", True, 1.0)
            L.append(fmt(metrics(eq, tr, f"{prof} only")))
        L.append("")
    (OUT / "phase4_portfolio.md").write_text("\n".join(L))
    json.dump(summary, open(OUT / "phase4_summary.json", "w"), indent=1, default=float)
    print("\n".join(L))


if __name__ == "__main__":
    main()
