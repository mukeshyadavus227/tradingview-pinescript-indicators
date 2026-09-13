#!/usr/bin/env python3
"""
Build the event table: one row per (symbol, bar, strategy, direction) where that
strategy's TRIGGER fired, regardless of score or alignment. This is the
population the whole validation runs on:

  - the DEPLOYED set is the subset with fired == True (winner, aligned,
    score >= minScore, R:R, liquidity, cooldown);
  - the ABLATION BASELINE is every trigger event with no score filter at all;
  - expectancy-by-decile is computed over trigger events within a strategy,
    which is the only comparison that isolates what the SCORE adds.

Every event carries that strategy's own stop/target geometry and is labelled
with the profile's horizon, so an S3 event is evaluated as an S3 trade even on
a bar where S4 won.

Output: events_<PROFILE>.csv in research/out/.
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import pine_ta as ta
from engine import run_engine, PROFILES, REGIME_NAMES, STRAT_NAMES
from labels import label_events

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
COMPONENTS = ("trend", "mom", "loc", "vol", "htf")


def events_for_symbol(sym, bars, profile):
    d = run_engine(bars, profile)
    c = d.c.values
    mt = 0.01
    rows = []
    for k in (1, 2, 3, 4):
        s = f"s{k}"
        for is_long, trig_col, raw_col in ((True, f"{s}_trigL", f"{s}_raw"), (False, f"{s}_trigS", f"{s}_rawS")):
            idx = np.where(d[trig_col].values & d.warmupOk.values)[0]
            if len(idx) == 0:
                continue
            stopD = d[f"{s}_stopD"].values if (is_long or k != 2) else d["s2_stopD_short"].values
            tpD = d[f"{s}_tpD"].values
            entry = ta.round_to_mintick(c[idx], mt)
            stop = ta.round_to_mintick(c[idx] - stopD[idx] if is_long else c[idx] + stopD[idx], mt)
            tp = ta.round_to_mintick(c[idx] + tpD[idx] if is_long else c[idx] - tpD[idx], mt)
            risk = np.abs(entry - stop)
            rr = np.where(risk > 0, np.abs(tp - entry) / risk, 0.0)
            aligned = d[f"{s}_al"].values[idx]
            winner = (d.bestStrat.values[idx] == k) & (d.isLong.values[idx] == is_long)
            for j, t in enumerate(idx):
                row = dict(symbol=sym, profile=profile.name, t_idx=int(t), date=str(d.date.values[t]),
                           strat=STRAT_NAMES[k], k=k, is_long=is_long, dir="L" if is_long else "S",
                           score=float(d[raw_col].values[t]), aligned=bool(aligned[j]),
                           regime=REGIME_NAMES[int(d.regime.values[t])], regimeConf=float(d.regimeConf.values[t]),
                           entry=float(entry[j]), stop=float(stop[j]), tp=float(tp[j]), rr=float(rr[j]),
                           liquidityOk=bool(d.liquidityOk.values[t]), winner=bool(winner[j]),
                           eligible=bool(d.eligible.values[t] and winner[j]), fired=bool(d.fired.values[t] and winner[j]),
                           atr=float(d.atr.values[t]), adx=float(d.adx.values[t]), rvPctile=float(d.rvPctile.values[t]),
                           dAtrPct=float(d.dAtrPct.values[t]), distFromHi=float(d.distFromHi.values[t]),
                           dMom121=float(d.dMom121.values[t]), dRoc20=float(d.dRoc20.values[t]),
                           compositeScore=float(d.compositeScore.values[t]))
                if is_long:
                    for cname in COMPONENTS:
                        row[f"c_{cname}"] = float(d[f"{s}_{cname}"].values[t])
                rows.append(row)
    labelled = label_events(bars, rows, profile.time_stop_days)
    return labelled


def main():
    syms = sorted(p.stem for p in DATA.glob("*.csv"))
    profiles = [PROFILES[n] for n in (sys.argv[1:] or PROFILES)]
    for profile in profiles:
        t0 = time.time()
        allrows = []
        for sym in syms:
            bars = pd.read_csv(DATA / f"{sym}.csv")
            allrows.extend(events_for_symbol(sym, bars, profile))
        ev = pd.DataFrame(allrows)
        ev.to_csv(OUT / f"events_{profile.name}.csv", index=False)
        fired = ev[ev.fired]
        print(f"{profile.name}: {len(syms)} symbols, {len(ev):,} trigger events, {int(ev.is_long.sum()):,} long, "
              f"{len(fired):,} fired  [{time.time()-t0:.0f}s]")
        print("  fired by strategy:", fired.strat.value_counts().to_dict())
        print("  fired by regime:  ", fired.regime.value_counts().to_dict())
        print("  fired exit reasons:", fired.reason.value_counts().to_dict())


if __name__ == "__main__":
    main()
