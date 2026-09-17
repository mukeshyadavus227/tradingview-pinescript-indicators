#!/usr/bin/env python3
"""
Generate mnq_mtf_swing_bt.pine — the strategy() twin — from mnq_mtf_swing.pine.

The twin is produced by TEXT TRANSFORMATION of the indicator source, not by
hand. That is the parity guarantee: every regime test, zone rule, state
transition and risk calculation in the twin is byte-identical to the indicator
because it is the same text. Only two things change:

  1. The `indicator(...)` declaration becomes `strategy(...)` with the settings
     that make the equity curve honest for MNQ.
  2. An execution block is appended that turns the indicator's own entryFired
     flag and SL/TP levels into orders.

Everything else is kept, including the alert() calls and the dashboard, because
a strategy may call all of them and every transformation skipped is one fewer
place for the two scripts to drift.

Usage:
    python build_twin.py            # regenerate ../mnq_mtf_swing_bt.pine
    python build_twin.py --check    # exit 1 if the committed twin is stale
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "mnq_mtf_swing.pine"
DST = HERE.parent / "mnq_mtf_swing_bt.pine"

BANNER = """\
// ============================================================================
// GENERATED FILE — DO NOT EDIT.
// Produced by research/build_twin.py from mnq_mtf_swing.pine. Edit the
// indicator and regenerate; `python research/build_twin.py --check` fails if
// this file is stale. The rules below are the SAME TEXT as the indicator,
// which is what makes a backtest of this file a backtest of that one.
//
// Read the Strategy Tester output against mnq_mtf_swing/README.md section
// "What still has to be proven": a profitable equity curve on a few months of
// 15M history is not evidence, and the number that matters is this system
// measured against the plain-fill null on the same setups.
// ============================================================================

"""

STRATEGY_DECL = """\
strategy("MNQ MTF Swing Long — BACKTEST TWIN", "MNQ-MTF-BT", overlay = true,
     max_bars_back = 2000, max_labels_count = 200, max_lines_count = 100,
     // ── settings that make the equity curve honest ────────────────────────
     calc_on_every_tick = false,            // decide on confirmed bars only
     process_orders_on_close = true,        // the entry fills at the signal bar's close
     fill_orders_on_standard_ohlc = true,   // no Heikin-Ashi / Renko fill fiction
     pyramiding = 0,                        // one position at a time
     initial_capital = 25000,
     default_qty_type = strategy.fixed, default_qty_value = 1,
     commission_type = strategy.commission.cash_per_contract, commission_value = 0.75,
     slippage = 2)"""

EXEC_BLOCK = """


// ╔══════════════════════════════════════════════════════════════════════════╗
// ║            STRATEGY EXECUTION  (twin only — appended by build_twin.py)   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The rules above decide the levels; this block only places the orders that
// realise them, so the twin's fills follow the same geometry the indicator
// draws and the webhook sends.
//
// The bracket is issued on the ENTRY bar as well as on every bar in the
// position. Under process_orders_on_close the entry fills at this bar's close
// AFTER the script has run, so strategy.position_size is still 0 here; an exit
// issued only once position_size > 0 would not exist during the next bar's
// intrabar path, while the indicator treats SL and TP as live from the bar
// after entry. Exit orders bound to a pending entry wait for its fill, so
// issuing them now makes them live exactly when the rules say they are.
//
// TradingView's broker emulator resolves a bar that touches both levels by its
// own path assumption, while the indicator and the Python mirror resolve it as
// STOP WINS. That is the one known place where the twin can print a better
// trade than the rules allow, and it biases the twin OPTIMISTICALLY. Count how
// many trades exit on a bar whose range spans both levels before trusting the
// headline number.
if entryFired
    strategy.entry("L", strategy.long, qty = 1, comment = tpSrc)

if state == ST_TRADE and (entryFired or strategy.position_size > 0)
    strategy.exit("L-x", "L", stop = slPx, limit = tpPx, comment_loss = "SL", comment_profit = "TP")

// The rules exited (roll window, or an exit the emulator did not take) but the
// emulator still holds the position: flatten it and tag it so the difference is
// visible in the trade list rather than hidden in the equity curve.
if strategy.position_size > 0 and state != ST_TRADE
    strategy.close_all(comment = "RESYNC")
"""


def build(src_text: str) -> str:
    lines = src_text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("indicator("))
    depth = 0
    end = None
    for i in range(start, len(lines)):
        depth += lines[i].count("(") - lines[i].count(")")
        if depth == 0:
            end = i
            break
    assert end is not None, "could not find the end of the indicator() declaration"
    out = lines[:start] + STRATEGY_DECL.split("\n") + lines[end + 1:]
    text = "\n".join(out)
    assert not re.search(r"^indicator\(", text, re.M), "twin still declares an indicator"
    # The banner goes directly BELOW the version annotation so the twin keeps
    # the same header shape as the indicator and //@version=6 stays at the top.
    marker = "//@version=6\n"
    hdr = text.index(marker) + len(marker)
    text = text[:hdr] + BANNER + text[hdr:]
    return text.rstrip("\n") + EXEC_BLOCK


def main():
    generated = build(SRC.read_text())
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
