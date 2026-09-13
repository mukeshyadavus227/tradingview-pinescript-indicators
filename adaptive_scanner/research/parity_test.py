#!/usr/bin/env python3
"""
Parity gate: the Strategy Tester's trade list for asr_engine_bt.pine on one
symbol versus the Python mirror's sequential replay of the same symbol.

Nothing in the walk-forward is trustworthy until this passes, because until it
does the Python results describe a different system than the one that trades.

The replay is simulate.simulate_symbol with the deployed v3 parameters
(engine.V3_DEPLOYED), the v3 exit models (simulate.EXITS_V3) and the close
fill — the same call that produced phase3_final.md and the `close` rows of
phase6_fill_baseline.md — so the gate validates exactly the trade list the
findings are built on. The twin fills at the signal close by design
(process_orders_on_close); the deployable next-open fill is a server-side rule
(PHASE6_FINDINGS.md) and is not what this gate tests.

How to produce the TradingView side
  1. Open the symbol on a 1D chart with the chart timezone set to Exchange, so
     daily fills print the session date. Add asr_engine_bt.pine (the generated
     twin, not the indicator). Inputs: Profile = SWING or POSITIONAL; leave
     everything else at its default. There is no "only when flat" or "time
     stop" input to set: the engine is one-position-per-chart by construction
     (fireSignal requires posSide == 0) and the S1 time stop is the profile's.
  2. Strategy Tester → List of Trades → Export data (CSV). One row per entry
     and one per exit, paired by "Trade #". TradingView reports a partial exit
     as a separate trade number that repeats the entry; the parser collapses
     those into one trade per entry and keeps the final leg.
  3. python parity_test.py SPY SWING <exported.csv>
     Repeat per symbol and profile, then `python parity_test.py --summary`
     pools the out/parity_*.json results: on one symbol n is 40-80 trades and
     a single mismatch is already below 99%.

Data. research/data_parity/<SYMBOL>.csv (5,000 daily bars from the same
TradingView feed as data/, 0 differing rows on the 3,000-bar overlap) is
preferred over data/<SYMBOL>.csv so the mirror's weekly EMA(50) seeding has
converged well before the comparison window. The window defaults to
[first bar + 4 years, last bar]; --window-start / --window-end override it.
TradingView's own history for SPY starts in 1993, so export trades before the
window are dropped, not counted.

Match criterion, trade for trade: same entry bar; entry price within 1.5
ticks; final exit on the same bar at a price within 1.5 ticks; same exit
reason class (SL / BE / TRAIL / TIME / OPEN). The twin carries slippage = 1
tick, so its entries print one tick above the signal close and its stop and
market exits one tick below the level; the extra half tick absorbs the
export's display rounding of a gap fill at an off-grid open (TradingView's
SPY data has opens like 208.045).

Every mismatch is attributed where the signature is unambiguous:
  POC_CLOSE_ATTEMPT  the engine raised the stop at a bar's close to a level at
                     or above that close. With process_orders_on_close the
                     Strategy Tester fills the re-issued stop at that close;
                     the engine and the labeller exit on the next bar. The
                     replay flags every exposed trade (poc_date) and prints
                     the count even when the export matches.
  RESYNC             the twin's guard flattened at a close because the broker
                     emulator had not filled a level the engine had booked.
  TIME_1BAR          both sides TIME, one bar apart (time anchor).
  PARTIAL_LEG        the export's final leg is a partial fill: parser problem.
  SEQUENCE           a one-sided entry that falls inside the other side's
                     holding period: a cascade from an earlier divergence.
  WINDOW_EDGE        a one-sided first trade, blocked on the other side by a
                     position opened before the window.
Anything else prints as ENTRY / EXIT_DATE / EXIT_PRICE / REASON /
MISSING_TV / MISSING_PY.

Modes
  python parity_test.py SYM PROFILE                    replay only, print the Python trades
  python parity_test.py SYM PROFILE export.csv [...]   the gate
  python parity_test.py --summary                      pool out/parity_*.json
  python parity_test.py --selftest                     harness self-test on synthetic exports
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from engine import PROFILES, V3_DEPLOYED
from simulate import simulate_symbol, EXITS_V3

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TICK = 0.01
TOL_TICKS = 1.5           # slippage = 1 tick in the twin, plus display rounding of an off-grid fill (gap at an open like 208.045)
SEED_YEARS = 4            # weekly EMA(50): residual seed error e^-8 after 208 weeks
GATE = 0.99
ET = "America/New_York"

MODERN_COLS = ["Trade #", "Type", "Date/Time", "Signal", "Price USD", "Position size (qty)", "Position size (value)",
               "Net P&L USD", "Net P&L %", "Run-up USD", "Run-up %", "Drawdown USD", "Drawdown %",
               "Cumulative P&L USD", "Cumulative P&L %"]
LEGACY_COLS = ["Trade #", "Type", "Signal", "Date/Time", "Price", "Contracts", "Profit", "Profit %",
               "Cum. Profit", "Cum. Profit %", "Run-up", "Run-up %", "Drawdown", "Drawdown %"]


# ────────────────────────────────────────────────────────────────────────────
# Python side
# ────────────────────────────────────────────────────────────────────────────
def load_bars(sym):
    p = HERE / "data_parity" / f"{sym}.csv"
    src = p if p.exists() else HERE / "data" / f"{sym}.csv"
    if not src.exists():
        raise SystemExit(f"no bars for {sym}: expected {p} or {HERE / 'data' / (sym + '.csv')}")
    return pd.read_csv(src), src


def bar_dates(bars):
    """Session dates (ET) of the daily bars, as naive Timestamps — the key both trade lists are compared on."""
    return pd.to_datetime(bars.t.values, unit="s", utc=True).tz_convert(ET).normalize().tz_localize(None)


def default_window(bars):
    d = bar_dates(bars)
    return d[0] + pd.DateOffset(years=SEED_YEARS), d[-1]


def sequential_replay(sym, bars, prof_name, tick=TICK):
    """One position per chart, cooldown, v3 exits, close fill: the deployed profile as the findings simulate it."""
    tr = simulate_symbol(sym, bars, PROFILES[prof_name], V3_DEPLOYED[prof_name], EXITS_V3, fill="close", mintick=tick)
    df = pd.DataFrame(tr)
    if len(df) == 0:
        return pd.DataFrame(columns=["entry_date", "entry", "side", "strat", "k", "exit_date", "exit", "reason", "R", "bars",
                                     "partial_date", "partial_px", "poc_date", "poc_px"])
    df = df.rename(columns={"date": "entry_date", "exit_px": "exit"})
    df["side"] = "L"
    for c in ("entry_date", "exit_date", "partial_date", "poc_date"):
        df[c] = pd.to_datetime(df[c])
    return df[["entry_date", "entry", "side", "strat", "k", "exit_date", "exit", "reason", "R", "bars",
               "partial_date", "partial_px", "poc_date", "poc_px"]].reset_index(drop=True)


# ────────────────────────────────────────────────────────────────────────────
# TradingView side
# ────────────────────────────────────────────────────────────────────────────
def reason_class(r):
    r = str(r).upper().strip()
    for pref, cls in (("SL", "SL"), ("STOP", "SL"), ("BE", "BE"), ("TRAIL", "TRAIL"), ("TP", "TP"),
                      ("PARTIAL", "PARTIAL"), ("TIME", "TIME"), ("RESYNC", "RESYNC")):
        if r.startswith(pref):
            return cls
    if r in ("EOD", "OPEN", "EOD_FLAT", "NAN", "NONE", ""):
        return "OPEN"
    return r


def _col(cols, pred):
    for c in cols:
        if pred(str(c).lower().strip()):
            return c
    return None


def parse_tv_export(path):
    """Strategy Tester export → one row per trade (entry + final exit), both header generations accepted."""
    raw = pd.read_csv(path)
    cols = list(raw.columns)
    c_trade = _col(cols, lambda s: s.startswith("trade"))
    c_type = _col(cols, lambda s: s == "type")
    c_dt = _col(cols, lambda s: s.startswith("date"))
    c_sig = _col(cols, lambda s: s.startswith("signal"))
    c_px = _col(cols, lambda s: s.startswith("price"))
    missing = [n for n, c in (("Trade #", c_trade), ("Type", c_type), ("Date/Time", c_dt), ("Price", c_px)) if c is None]
    if missing:
        raise SystemExit(f"export is missing columns {missing}; found {cols}")
    raw = raw.dropna(subset=[c_type])
    rows = pd.DataFrame({
        "trade": raw[c_trade].values,
        "typ": raw[c_type].astype(str).str.lower().str.strip().values,
        "when": pd.to_datetime(raw[c_dt], errors="coerce").values,
        "px": pd.to_numeric(raw[c_px].astype(str).str.replace(",", "", regex=False), errors="coerce").values,
        "sig": (raw[c_sig].astype(str).str.strip().values if c_sig else np.array([""] * len(raw))),
    })
    rows["when"] = pd.to_datetime(rows["when"])
    by_entry = {}
    for n, g in rows.groupby("trade", sort=False):
        ent = g[g.typ.str.contains("entry")]
        ex = g[g.typ.str.contains("exit")]
        if len(ent) == 0:
            continue
        e = ent.iloc[0]
        if pd.isna(e.when):
            raise SystemExit(f"unparseable Date/Time on trade {n}: {raw.loc[e.name, c_dt]!r}")
        key = (e.when.normalize(), round(float(e.px), 6))
        t = by_entry.setdefault(key, dict(entry_date=e.when.normalize(), entry=float(e.px),
                                          side="S" if "short" in e.typ else "L", entry_sig=str(e.sig), legs=[]))
        for _, x in ex.iterrows():
            is_open = str(x.sig).strip().lower() == "open" or pd.isna(x.px)
            t["legs"].append(dict(exit_date=(pd.NaT if is_open else x.when.normalize()), exit=(np.nan if is_open else float(x.px)),
                                  reason=("OPEN" if is_open else str(x.sig).strip()), trade=n))
    out = []
    for t in by_entry.values():
        legs = sorted(t["legs"], key=lambda L: (pd.Timestamp.max if pd.isna(L["exit_date"]) else L["exit_date"],
                                                0 if reason_class(L["reason"]) == "PARTIAL" else 1))
        final = legs[-1] if legs else dict(exit_date=pd.NaT, exit=np.nan, reason="OPEN")
        out.append(dict(entry_date=t["entry_date"], entry=t["entry"], side=t["side"], entry_sig=t["entry_sig"],
                        exit_date=final["exit_date"], exit=final["exit"], reason=final["reason"], n_legs=len(legs),
                        tv_trades=",".join(str(L["trade"]) for L in legs)))
    df = pd.DataFrame(out, columns=["entry_date", "entry", "side", "entry_sig", "exit_date", "exit", "reason", "n_legs", "tv_trades"])
    df["entry_date"] = pd.to_datetime(df["entry_date"]); df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df.sort_values("entry_date").reset_index(drop=True)


# ────────────────────────────────────────────────────────────────────────────
# Comparison
# ────────────────────────────────────────────────────────────────────────────
def _inside(date, trades):
    """True if `date` falls inside the holding period (entry, exit] of any trade in `trades`."""
    for _, x in trades.iterrows():
        end = x.exit_date if pd.notna(x.exit_date) else pd.Timestamp.max
        if x.entry_date < date <= end:
            return True
    return False


def compare(py, tv, bars, window, tick=TICK):
    w0, w1 = window
    dates = bar_dates(bars)
    idx = {d: i for i, d in enumerate(dates)}
    py = py[(py.entry_date >= w0) & (py.entry_date <= w1)].copy()
    tv_pre = tv[tv.entry_date < w0]
    tv = tv[(tv.entry_date >= w0) & (tv.entry_date <= w1)].copy()
    m = py.merge(tv, on="entry_date", how="outer", suffixes=("_py", "_tv"), indicator=True).sort_values("entry_date")
    both = m[m._merge == "both"].copy()
    only_py = m[m._merge == "left_only"].copy()
    only_tv = m[m._merge == "right_only"].copy()

    tol = TOL_TICKS * tick + 1e-9
    ok_entry = (both.entry_py - both.entry_tv).abs() <= tol
    same_date = (both.exit_date_py == both.exit_date_tv) | (both.exit_date_py.isna() & both.exit_date_tv.isna())
    same_px = ((both.exit_py - both.exit_tv).abs() <= tol) | (both.exit_py.isna() & both.exit_tv.isna())
    ok_exit = same_date & same_px
    ok_reason = both.reason_py.map(reason_class) == both.reason_tv.map(reason_class)
    full = ok_entry & ok_exit & ok_reason
    both["full"] = full

    def attribute(r):
        rc_py, rc_tv = reason_class(r.reason_py), reason_class(r.reason_tv)
        if rc_tv == "PARTIAL":
            return "PARTIAL_LEG"
        if rc_tv == "RESYNC":
            return "RESYNC"
        if pd.notna(r.poc_date) and pd.notna(r.exit_date_tv) and r.exit_date_tv == r.poc_date \
                and abs(float(r.exit_tv) - float(r.poc_px)) <= 2 * tick + 1e-9 and rc_tv in ("BE", "TRAIL"):
            return "POC_CLOSE_ATTEMPT"
        if rc_py == "TIME" and rc_tv == "TIME" and pd.notna(r.exit_date_py) and pd.notna(r.exit_date_tv) \
                and abs(idx.get(r.exit_date_py, -9) - idx.get(r.exit_date_tv, 9)) == 1:
            return "TIME_1BAR"
        if abs(float(r.entry_py) - float(r.entry_tv)) > tol:
            return "ENTRY"
        if not ((r.exit_date_py == r.exit_date_tv) or (pd.isna(r.exit_date_py) and pd.isna(r.exit_date_tv))):
            return "EXIT_DATE"
        if not ((abs(float(r.exit_py) - float(r.exit_tv)) <= tol) or (pd.isna(r.exit_py) and pd.isna(r.exit_tv))):
            return "EXIT_PRICE"
        return "REASON"

    both["cause"] = [("" if f else attribute(r)) for f, (_, r) in zip(full, both.iterrows())]
    first_py = py.entry_date.min() if len(py) else None
    causes_py, causes_tv = [], []
    for _, r in only_py.iterrows():
        if r.entry_date == first_py and len(tv_pre) and (tv_pre.exit_date.isna() | (tv_pre.exit_date >= r.entry_date)).any():
            causes_py.append("WINDOW_EDGE")
        elif _inside(r.entry_date, tv):
            causes_py.append("SEQUENCE")
        else:
            causes_py.append("MISSING_TV")
    for _, r in only_tv.iterrows():
        causes_tv.append("SEQUENCE" if _inside(r.entry_date, py) else "MISSING_PY")
    only_py["cause"] = causes_py
    only_tv["cause"] = causes_tv
    n = max(len(py), len(tv))
    causes = {}
    for c in list(both.cause[both.cause != ""]) + causes_py + causes_tv:
        causes[c] = causes.get(c, 0) + 1
    bad_dates = sorted(list(both.entry_date[~full]) + list(only_py.entry_date) + list(only_tv.entry_date))
    return dict(py=py, tv=tv, both=both, only_py=only_py, only_tv=only_tv, n=n, full=int(full.sum()),
                pct=(full.sum() / n if n else 1.0), ok_entry=int(ok_entry.sum()), ok_exit=int(ok_exit.sum()),
                ok_reason=int(ok_reason.sum()), causes=causes, first_divergence=(bad_dates[0] if bad_dates else None),
                poc_exposed=int(py.poc_date.notna().sum()), window=(w0, w1))


def report(sym, prof_name, res, src, export=None):
    w0, w1 = res["window"]
    print(f"{sym} {prof_name}: bars from {src.name}, window {w0.date()} → {w1.date()}")
    print(f"  python replay {len(res['py'])} trades, TradingView export {len(res['tv'])} trades"
          + (f" ({export})" if export else ""))
    both = res["both"]
    print(f"  matched on entry date: {len(both)}   python-only: {len(res['only_py'])}   tv-only: {len(res['only_tv'])}")
    print(f"  entry price ok: {res['ok_entry']}/{len(both)}   exit date+price ok: {res['ok_exit']}/{len(both)}   reason ok: {res['ok_reason']}/{len(both)}")
    print(f"  FULL trade-for-trade match: {res['full']}/{res['n']} = {res['pct']:.1%}   (gate: ≥ {GATE:.0%})")
    print(f"  POC-exposed python trades (exit would print one bar early in the Strategy Tester): {res['poc_exposed']}")
    if res["causes"]:
        print("  mismatch attribution:", ", ".join(f"{k} ×{v}" for k, v in sorted(res["causes"].items(), key=lambda kv: -kv[1])))
        print(f"  first divergence: {res['first_divergence'].date()}")
    bad = both[~both.full]
    if len(bad):
        print("\n  mismatches:")
        cols = ["entry_date", "cause", "entry_py", "entry_tv", "exit_date_py", "exit_date_tv", "exit_py", "exit_tv", "reason_py", "reason_tv"]
        print(bad[cols].head(40).to_string(index=False))
    if len(res["only_py"]):
        print("\n  python-only entries:", [(d.date().isoformat(), c) for d, c in zip(res["only_py"].entry_date, res["only_py"].cause)][:20])
    if len(res["only_tv"]):
        print("\n  tv-only entries:", [(d.date().isoformat(), c) for d, c in zip(res["only_tv"].entry_date, res["only_tv"].cause)][:20])


def save_result(sym, prof_name, res, export):
    OUT.mkdir(exist_ok=True)
    w0, w1 = res["window"]
    payload = dict(symbol=sym, profile=prof_name, export=str(export), window=[w0.date().isoformat(), w1.date().isoformat()],
                   n_py=len(res["py"]), n_tv=len(res["tv"]), matched=len(res["both"]), full=res["full"], n=res["n"],
                   pct=res["pct"], causes=res["causes"], poc_exposed=res["poc_exposed"],
                   first_divergence=(res["first_divergence"].date().isoformat() if res["first_divergence"] is not None else None))
    p = OUT / f"parity_{sym}_{prof_name}.json"
    p.write_text(json.dumps(payload, indent=1))
    return p


def summary():
    files = sorted(OUT.glob("parity_*.json"))
    if not files:
        print("no out/parity_*.json results yet"); return 1
    rows = [json.loads(f.read_text()) for f in files]
    print("| symbol | profile | window | python | tv | full match | % | attribution |")
    print("|---|---|---|---:|---:|---:|---:|---|")
    for r in rows:
        print(f"| {r['symbol']} | {r['profile']} | {r['window'][0]} → {r['window'][1]} | {r['n_py']} | {r['n_tv']} | {r['full']}/{r['n']} | {r['pct']:.1%} | "
              + (", ".join(f"{k} ×{v}" for k, v in r['causes'].items()) or "—") + " |")
    full, n = sum(r["full"] for r in rows), sum(r["n"] for r in rows)
    pct = full / n if n else 1.0
    print(f"\npooled: {full}/{n} = {pct:.2%}   gate ≥ {GATE:.0%}: {'PASS' if pct >= GATE else 'FAIL'}")
    return 0 if pct >= GATE else 1


# ────────────────────────────────────────────────────────────────────────────
# Self-test: synthetic exports in TradingView's shape, from the replay itself.
# Tests the parser, the pairing, the window and the attribution — not parity.
# ────────────────────────────────────────────────────────────────────────────
def synth_export(py, bars, path, legacy=False, tick=TICK, perturb=None):
    """Write an export the way the twin would report the replay: slippage = 1 tick on market/stop fills,
    none on the partial limit; a partial exit split into its own trade number that repeats the entry;
    an open trade closed with Signal 'Open' on the last bar."""
    dates = bar_dates(bars)
    last_dt, last_c = dates[-1], float(bars.c.iloc[-1])
    rows, n = [], 0
    perturb = perturb or {}

    def row(n, typ, dt, sig, px):
        r = {"Trade #": n, "Type": typ, "Date/Time": dt.strftime("%Y-%m-%d %H:%M"), "Signal": sig,
             ("Price" if legacy else "Price USD"): f"{px:.2f}"}
        for c in (LEGACY_COLS if legacy else MODERN_COLS):
            r.setdefault(c, 0)
        rows.append(r)

    for _, t in py.iterrows():
        if t.entry_date in perturb.get("drop", []):
            continue
        entry_px = t.entry + tick
        legs = []
        if pd.notna(t.partial_date):
            legs.append((t.partial_date, float(t.partial_px), "PARTIAL"))
        rc = reason_class(t.reason)
        if t.entry_date in perturb.get("poc", []):          # the Strategy Tester's close-attempt exit
            legs.append((t.poc_date, float(t.poc_px) - tick, "TRAIL"))
        elif t.entry_date in perturb.get("time_shift", []):
            legs.append((dates[dates.get_loc(t.exit_date) + 1], float(t.exit) - tick, "TIME"))
        elif rc == "OPEN":
            legs.append((None, None, "OPEN"))
        else:
            legs.append((t.exit_date, float(t.exit) - tick, rc))
        for d, px, why in legs:
            n += 1
            row(n, "Entry long", t.entry_date + pd.Timedelta(hours=9, minutes=30), f"MOM {int(np.random.default_rng(n).integers(70, 99))}", entry_px)
            if why == "OPEN":
                row(n, "Exit long", last_dt + pd.Timedelta(hours=16), "Open", last_c)
            else:
                row(n, "Exit long", d + pd.Timedelta(hours=16), why, px)
    for d, px in perturb.get("extra", []):
        n += 1
        row(n, "Entry long", d + pd.Timedelta(hours=9, minutes=30), "MTF 80", px + tick)
        row(n, "Exit long", d + pd.Timedelta(days=3, hours=16), "SL", px * 0.97)
    cols = LEGACY_COLS if legacy else MODERN_COLS
    pd.DataFrame(rows)[cols].to_csv(path, index=False)
    return path


def selftest(sym="SPY"):
    import tempfile
    bars, src = load_bars(sym)
    window = default_window(bars)
    ok = True
    with tempfile.TemporaryDirectory() as td:
        for prof_name in ("SWING", "POSITIONAL"):
            py = sequential_replay(sym, bars, prof_name)
            for legacy in (False, True):
                p = synth_export(py, bars, Path(td) / f"{sym}_{prof_name}_{'legacy' if legacy else 'modern'}.csv", legacy=legacy)
                res = compare(py, parse_tv_export(p), bars, window)
                tag = f"{prof_name} {'legacy' if legacy else 'modern'} headers"
                good = res["pct"] == 1.0 and not res["causes"] and res["n"] == len(py[(py.entry_date >= window[0]) & (py.entry_date <= window[1])])
                print(f"  faithful export, {tag}: {res['full']}/{res['n']} = {res['pct']:.1%} {'OK' if good else 'FAIL'}")
                ok &= good
            # perturbed export: one trade dropped, one exposed trade exited at the close-attempt, one TIME shifted, one spurious entry
            pw = py[(py.entry_date >= window[0]) & (py.entry_date <= window[1])]
            pert = {"drop": [pw.entry_date.iloc[len(pw) // 2]]}
            poc = pw[pw.poc_date.notna()]
            if len(poc):
                pert["poc"] = [poc.entry_date.iloc[0]]
            tm = pw[pw.reason == "TIME"]
            if len(tm):
                pert["time_shift"] = [tm.entry_date.iloc[0]]
            mid = pw.iloc[len(pw) // 3]
            if pd.notna(mid.exit_date) and (mid.exit_date - mid.entry_date).days > 5:
                pert["extra"] = [(mid.entry_date + pd.Timedelta(days=2), float(mid.entry))]
                # land the spurious entry on a bar (the merge is on session dates)
                d = bar_dates(bars)
                pert["extra"] = [(d[d.get_loc(mid.entry_date) + 1], float(mid.entry))]
            p = synth_export(py, bars, Path(td) / f"{sym}_{prof_name}_perturbed.csv", perturb=pert)
            res = compare(py, parse_tv_export(p), bars, window)
            expect = {"MISSING_TV"} | ({"POC_CLOSE_ATTEMPT"} if "poc" in pert else set()) \
                | ({"TIME_1BAR"} if "time_shift" in pert else set()) | ({"SEQUENCE"} if "extra" in pert else set())
            got = set(res["causes"])
            good = expect <= got and res["pct"] < 1.0
            print(f"  perturbed export, {prof_name}: {res['full']}/{res['n']} = {res['pct']:.1%}; attributed {res['causes']} "
                  f"(expected ⊇ {sorted(expect)}) {'OK' if good else 'FAIL'}")
            ok &= good
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ────────────────────────────────────────────────────────────────────────────
def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol", nargs="?")
    ap.add_argument("profile", nargs="?")
    ap.add_argument("export", nargs="?")
    ap.add_argument("--window-start")
    ap.add_argument("--window-end")
    ap.add_argument("--tick", type=float, default=TICK)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.summary:
        return summary()
    if a.selftest:
        return selftest(a.symbol or "SPY")
    if not (a.symbol and a.profile):
        ap.print_help(); return 2
    sym, prof_name = a.symbol, a.profile.upper()
    if prof_name not in PROFILES:
        raise SystemExit(f"profile must be one of {list(PROFILES)}")
    bars, src = load_bars(sym)
    py = sequential_replay(sym, bars, prof_name, a.tick)
    w0, w1 = default_window(bars)
    if a.window_start:
        w0 = pd.Timestamp(a.window_start)
    if a.window_end:
        w1 = pd.Timestamp(a.window_end)
    if a.export is None:                      # replay-only mode
        pw = py[(py.entry_date >= w0) & (py.entry_date <= w1)]
        print(f"{sym} {prof_name}: bars from {src.name}; window {w0.date()} → {w1.date()}: {len(pw)} of {len(py)} sequential trades")
        print(pw.drop(columns=["side"]).to_string(index=False))
        print(f"\nmean R {pw.R.mean():+.3f}; POC-exposed {int(pw.poc_date.notna().sum())}; reasons {pw.reason.value_counts().to_dict()}")
        return 0
    tv = parse_tv_export(a.export)
    res = compare(py, tv, bars, (w0, w1), a.tick)
    report(sym, prof_name, res, src, a.export)
    p = save_result(sym, prof_name, res, a.export)
    print(f"\n  saved {p.relative_to(HERE)}; pool with: python parity_test.py --summary")
    return 0 if res["pct"] >= GATE else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
