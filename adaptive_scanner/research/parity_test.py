#!/usr/bin/env python3
"""
Parity gate: the Strategy Tester's trade list for asr_engine_bt.pine on one
symbol versus this mirror's sequential replay of the same symbol.

Nothing in the walk-forward is trustworthy until this passes, because until it
does the Python results describe a different system than the one that trades.

How to produce the TradingView side:
  1. Load data/<SYMBOL>.csv's symbol on a 1D chart, add asr_engine_bt.pine,
     set Profile to SWING or POSITIONAL, leave every other input at default,
     BT: take signals only when flat = ON, BT: enforce profile time stop = ON.
  2. Strategy Tester → List of Trades → Export (the CSV has one row per entry
     and one per exit, paired by "Trade #").
  3. python parity_test.py <SYMBOL> <PROFILE> <exported.csv>

The match criterion is trade-for-trade: same entry bar (date), entry price
within one tick, exit date and exit price within one tick, same exit reason
class. The report lists every mismatch so the cause can be attributed.

Known acceptable differences:
  - TIME exits may land one bar apart if strategy.opentrades.entry_time
    resolves to the entry bar's close rather than its open. If every TIME
    mismatch is exactly +1 bar, adjust HORIZON_ANCHOR below and re-run.
  - TradingView's daily data may be dividend-adjusted differently from the
    CSV snapshot in data/. Re-fetch the CSV on the same day as the export.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from engine import run_engine, PROFILES
from labels import label_event

HERE = Path(__file__).resolve().parent
HORIZON_ANCHOR = "open"   # "open" = time[t]; "close" = time_close[t]
TICK = 0.01


def sequential_replay(bars, profile):
    """Single-position replay matching the twin with bt_onlyWhenFlat=True, pyramiding=0."""
    d = run_engine(bars, profile)
    o, h, l, c = (bars[k].values.astype(float) for k in "ohlc")
    time_ms = bars.t.values.astype(np.int64) * 1000
    trades = []
    busy_until = -1
    for t in np.where(d.fired.values)[0]:
        if t <= busy_until:
            continue
        lab = label_event(o, h, l, c, time_ms, int(t), bool(d.isLong.values[t]),
                          float(d.entryRef.values[t]), float(d.stopPrice.values[t]), float(d.tpPrice.values[t]),
                          profile.time_stop_days)
        if lab is None:
            continue
        busy_until = lab["exit_idx"]
        trades.append(dict(entry_date=str(d.date.values[t]), entry=float(d.entryRef.values[t]),
                           side="L" if d.isLong.values[t] else "S", strat=int(d.bestStrat.values[t]),
                           exit_date=str(d.date.values[lab["exit_idx"]]), exit=float(lab["exit_price"]),
                           reason=lab["reason"], R=float(lab["R"])))
    return pd.DataFrame(trades)


def parse_tv_export(path):
    """Pair the Strategy Tester export's entry/exit rows into one row per trade."""
    raw = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in raw.columns}
    tn = cols.get("trade #") or cols.get("trade")
    typ, sig, dt, px = cols["type"], cols.get("signal", cols.get("type")), cols["date/time"], cols["price"]
    out = []
    for n, g in raw.groupby(tn):
        ent = g[g[typ].str.contains("Entry", case=False)]
        ex = g[g[typ].str.contains("Exit", case=False)]
        if len(ent) == 0:
            continue
        e, x = ent.iloc[0], (ex.iloc[0] if len(ex) else None)
        side = "L" if "long" in str(e[typ]).lower() else "S"
        out.append(dict(entry_date=pd.to_datetime(e[dt]).strftime("%Y-%m-%d"), entry=float(e[px]), side=side,
                        exit_date=pd.to_datetime(x[dt]).strftime("%Y-%m-%d") if x is not None else None,
                        exit=float(x[px]) if x is not None else np.nan,
                        reason=str(x[sig]) if x is not None else "OPEN"))
    return pd.DataFrame(out)


def reason_class(r):
    r = str(r).upper()
    if r.startswith("TP"):
        return "TP"
    if r.startswith("SL"):
        return "SL"
    if "TIME" in r:
        return "TIME"
    return r


def main():
    sym, prof_name, export = sys.argv[1], sys.argv[2].upper(), sys.argv[3]
    profile = PROFILES[prof_name]
    bars = pd.read_csv(HERE / "data" / f"{sym}.csv")
    py = sequential_replay(bars, profile)
    tv = parse_tv_export(export)
    print(f"{sym} {prof_name}: python replay {len(py)} trades, TradingView export {len(tv)} trades")
    m = py.merge(tv, on="entry_date", how="outer", suffixes=("_py", "_tv"), indicator=True)
    only_py = m[m._merge == "left_only"]; only_tv = m[m._merge == "right_only"]; both = m[m._merge == "both"]
    ok_entry = (np.abs(both.entry_py - both.entry_tv) <= TICK + 1e-9)
    ok_exit = (np.abs(both.exit_py - both.exit_tv) <= TICK + 1e-9) & (both.exit_date_py == both.exit_date_tv)
    ok_reason = both.reason_py.map(reason_class) == both.reason_tv.map(reason_class)
    full = ok_entry & ok_exit & ok_reason
    n = max(len(py), len(tv))
    print(f"  matched on entry date: {len(both)}  python-only: {len(only_py)}  tv-only: {len(only_tv)}")
    print(f"  entry price ok: {ok_entry.sum()}/{len(both)}   exit date+price ok: {ok_exit.sum()}/{len(both)}   reason ok: {ok_reason.sum()}/{len(both)}")
    print(f"  FULL trade-for-trade match: {full.sum()}/{n} = {full.sum()/n:.1%}   (gate: ≥ 99%)")
    bad = both[~full]
    if len(bad):
        print("\n  mismatches:")
        print(bad[["entry_date", "entry_py", "entry_tv", "exit_date_py", "exit_date_tv", "exit_py", "exit_tv", "reason_py", "reason_tv"]].head(40).to_string(index=False))
    if len(only_py):
        print("\n  python-only entries:", only_py.entry_date.tolist()[:20])
    if len(only_tv):
        print("\n  tv-only entries:", only_tv.entry_date.tolist()[:20])
    sys.exit(0 if full.sum() / n >= 0.99 else 1)


if __name__ == "__main__":
    if len(sys.argv) == 3:   # replay-only mode: python parity_test.py SYMBOL PROFILE
        sym, prof_name = sys.argv[1], sys.argv[2].upper()
        py = sequential_replay(pd.read_csv(HERE / "data" / f"{sym}.csv"), PROFILES[prof_name])
        print(py.to_string(index=False)); print(f"\n{len(py)} sequential trades, mean R {py.R.mean():+.3f}")
    else:
        main()
