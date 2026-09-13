#!/usr/bin/env python3
"""
Generate asr_engine_bt.pine — the strategy() twin — from asr_engine.pine.

The twin is produced by TEXT TRANSFORMATION of the indicator source, not by
hand. That is the parity guarantee: every line of regime detection, scoring,
winner selection and risk math in the twin is byte-identical to the indicator
because it is the same text. Only two things change:

  1. The `indicator(...)` declaration becomes `strategy(...)` with the
     backtest settings that make the equity curve honest.
  2. A strategy-execution block is appended that turns `fireSignal` into
     entries with bracket exits and a time stop.

Everything else — the alert() call, the dashboard, the plots — is kept, because
strategies may call all of them and every transformation we skip is one fewer
place for the two scripts to drift.

Usage:
    python build_twin.py            # regenerate ../asr_engine_bt.pine
    python build_twin.py --check    # exit 1 if the committed twin is stale
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "asr_engine.pine"
DST = HERE.parent / "asr_engine_bt.pine"

BANNER = """\
// ============================================================================
// GENERATED FILE — DO NOT EDIT.
// Produced by research/build_twin.py from asr_engine.pine. Edit the indicator
// and regenerate; `python research/build_twin.py --check` fails CI-style if
// this file is stale. The scoring, regime and risk math below is the SAME TEXT
// as the indicator, which is the parity guarantee for the validation harness.
// ============================================================================

"""

STRATEGY_DECL = """\
strategy("Adaptive Scanner Engine — BACKTEST TWIN", "ASR-BT", overlay = true,
     max_labels_count = 100, max_lines_count = 100, max_bars_back = 1000,
     // ── settings that make the equity curve honest ────────────────────────
     calc_on_every_tick = false,            // decide on confirmed bars only
     process_orders_on_close = true,        // fill entries at the signal bar's close = entryRef
     fill_orders_on_standard_ohlc = true,   // no Heikin-Ashi / Renko fill fiction
     pyramiding = 0,                        // one position at a time
     initial_capital = 100000,
     default_qty_type = strategy.fixed, default_qty_value = 1,
     commission_type = strategy.commission.percent, commission_value = 0.005,
     slippage = 1,
     margin_long = 100, margin_short = 100)"""

EXEC_BLOCK = """


// ╔══════════════════════════════════════════════════════════════════════════╗
// ║              STRATEGY EXECUTION  (twin only — appended by build_twin.py) ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The shared exit engine above decides the levels; this block only places the
// orders that realise them, so the twin's fills follow the same rules as the
// validation labeller. Sizing is risk-based, mirroring the executor's equities
// formula: shares = floor(max_risk / (price - stop)).
bt_riskPct = input.float(1.5, "BT: risk % of equity per trade", minval = 0.1, maxval = 5.0, step = 0.1,
     group = "Backtest Twin")

bt_qty = realRisk > 0 ? math.max(1, math.floor(strategy.equity * bt_riskPct / 100.0 / realRisk)) : 0

if fireSignal and bt_qty > 0
    strategy.entry("L", strategy.long, qty = bt_qty, comment = stratTag(bestStrat) + " " + str.tostring(bestScore, "#"))

// The bracket is issued on the ENTRY bar as well as on every bar in the
// position. With process_orders_on_close the entry fills at this bar's close,
// AFTER the script has run, so strategy.position_size is still 0 here; an exit
// issued only once position_size > 0 would not exist during the next bar's
// intrabar path, while the engine (and the labeller) treat the bracket as live
// from bar t+1. Exit orders bound to a pending entry wait for its fill, so
// issuing them now makes them live from the next bar — the bar the engine
// starts checking. Two exits: the partial leg (limit + stop on exit_partialPct
// of the position) and the remainder (stop only); once the partial has filled
// only the remainder is live. Re-issued every bar so the stop follows the engine.
if posSide == 1 and (fireSignal or strategy.position_size > 0)
    if not posPartialDone and not na(posPartial)
        strategy.exit("L-part", "L", qty_percent = exit_partialPct, limit = posPartial, stop = posStop, comment_profit = "PARTIAL", comment_loss = "SL")
    strategy.exit("L-rest", "L", stop = posStop, comment_loss = posStop == posStop0 ? "SL" : posStop == posEntry ? "BE" : "TRAIL")

// The engine has already set posSide to 0 on the bar it exits, so the reason
// must come from the engine's own event, not from posSide/posStrat. TIME is a
// market close at this bar's close (process_orders_on_close), which is what the
// labeller books. Anything else still open here is a genuine disagreement
// between the broker emulator and the engine: flatten it and tag it RESYNC so
// the parity test can attribute it instead of hiding it.
if strategy.position_size > 0 and posSide == 0
    strategy.close_all(comment = evExit and evExitWhy == "TIME" ? "TIME" : "RESYNC")
"""


def build(src_text: str) -> str:
    # Replace the multi-line indicator(...) declaration. It starts at the line
    # beginning with `indicator(` and ends at the first line that closes the
    # paren balance.
    lines = src_text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("indicator("))
    depth = 0
    end = None
    for i in range(start, len(lines)):
        depth += lines[i].count("(") - lines[i].count(")")
        if depth == 0:
            end = i
            break
    assert end is not None, "could not find end of indicator() declaration"
    out = lines[:start] + STRATEGY_DECL.split("\n") + lines[end + 1:]
    text = "\n".join(out)
    # Sanity: the twin must not still declare an indicator.
    assert not re.search(r"^indicator\(", text, re.M)
    # Insert banner after the licence header (first two comment lines).
    hdr_end = text.index("\n//@version=6")
    text = text[:hdr_end + 1] + BANNER + text[hdr_end + 1:]
    return text.rstrip("\n") + EXEC_BLOCK


def main():
    src = SRC.read_text()
    generated = build(src)
    if "--check" in sys.argv:
        current = DST.read_text() if DST.exists() else ""
        if current != generated:
            print(f"STALE: {DST.name} does not match regeneration from {SRC.name}", file=sys.stderr)
            sys.exit(1)
        print("twin is up to date")
        return
    DST.write_text(generated)
    print(f"wrote {DST} ({len(generated.splitlines())} lines)")


if __name__ == "__main__":
    main()
