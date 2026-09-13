"""Control: a long entry at EVERY bar's close (slots 2..22) with the S3i stop geometry, 2R target, EOD flat.
If this is as negative as the strategies, the window is the story, not the triggers."""
import numpy as np, pandas as pd
from pathlib import Path
from engine_intraday import run_intraday
from labels import label_event_v3, INTRADAY_MODELS
D15, DD = Path("data_15m"), Path("data")
M = {m.name: m for m in INTRADAY_MODELS}["I0_fixed2R_eod"]
spy = pd.read_csv(D15 / "SPY.csv.gz")
rows = []
rng = np.random.default_rng(1)
for p in sorted(D15.glob("*.csv.gz")):
    sym = p.stem.replace(".csv", "")
    b = pd.read_csv(p); d = run_intraday(b, pd.read_csv(DD / f"{sym}.csv"), spy)
    o, h, l, c = (b[k].values.astype(float) for k in "ohlc"); atr, tm = d.atr.values, b.t.values.astype(np.int64) * 1000
    idx = np.where(d.warm.values & d.liquidity.values & (d.slot.values >= 2) & (d.slot.values <= 22) & (d.bars_left.values >= 3))[0]
    idx = rng.choice(idx, size=min(400, len(idx)), replace=False)      # 400 random bars per symbol
    for t in idx:
        entry = round(c[t], 2); stop = round(c[t] - d.s3_stopD.values[t], 2); risk = entry - stop
        if risk <= 0: continue
        for bps in (0, 5):
            r = label_event_v3(o, h, l, c, atr, tm, int(t), True, entry, stop, entry + 2 * risk, 30, M, cost_bps=bps, flat_at_idx=int(d.eod_idx.values[t]))
            rows.append(dict(symbol=sym, date=d.date.values[t], bps=bps, R=r["R"], trend_up=bool(d.trend_up.values[t])))
ev = pd.DataFrame(rows)
for bps in (0, 5):
    for lbl, m in (("train", ev.date < "2026-06-15"), ("test", ev.date >= "2026-06-15")):
        e = ev[(ev.bps == bps) & m]
        print(f"random-entry control @ {bps} bps · {lbl}: n={len(e):,} mean R {e.R.mean():+.3f} hit {(e.R>0).mean():.0%} | uptrend only: {e[e.trend_up].R.mean():+.3f}")
