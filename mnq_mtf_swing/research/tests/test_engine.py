"""
Unit tests for the rule engine: the entry gate arithmetic, the exit rules, the
calendar helpers, and causality (no rule may read a bar that had not closed).

These are the only executable check on the logic in this environment — the Pine
compiler and a TradingView chart are not available here.
"""
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bars import Bars, load_csv_gz  # noqa: E402
import engine as E  # noqa: E402
from engine import CT, ET, Params, in_roll_window, is_last_bar_of_session, rt, run, third_friday  # noqa: E402

DATA = HERE.parent / "data"


# ---------------------------------------------------------------- tick rounding
def test_rt_rounds_to_quarter_ties_away_from_zero():
    assert rt(29058.13, 0.25) == 29058.25
    assert rt(29058.12, 0.25) == 29058.0
    assert rt(29058.125, 0.25) == 29058.25   # tie -> away from zero
    assert rt(29058.0, 0.25) == 29058.0


# ---------------------------------------------------------------- calendar
def test_third_friday_and_roll_window():
    assert third_friday(2026, 9) == datetime(2026, 9, 18).date()
    assert third_friday(2026, 12) == datetime(2026, 12, 18).date()
    sep15 = int(datetime(2026, 9, 15, 12, 0, tzinfo=ET).timestamp())
    sep10 = int(datetime(2026, 9, 10, 12, 0, tzinfo=ET).timestamp())
    assert in_roll_window(sep15, 3) is True      # 3 days before the Sep expiry
    assert in_roll_window(sep10, 3) is False
    assert in_roll_window(sep15, 0) is False     # 0 disables the rule


def test_last_bar_of_session_is_the_bar_closing_into_the_halt():
    # 15:45 Chicago = the 15M bar closing at 16:00 CT, when the daily halt starts.
    assert is_last_bar_of_session(int(datetime(2026, 9, 15, 15, 45, tzinfo=CT).timestamp())) is True
    assert is_last_bar_of_session(int(datetime(2026, 9, 15, 15, 30, tzinfo=CT).timestamp())) is False
    assert is_last_bar_of_session(int(datetime(2026, 9, 15, 17, 45, tzinfo=CT).timestamp())) is False


# ---------------------------------------------------------------- exit rules
def _trade_bars(rows, start="2026-04-06 09:00"):
    """Build a Bars object from (o,h,l,c) rows on a 15M grid."""
    t0 = int(datetime.fromisoformat(start).replace(tzinfo=ET).timestamp())
    t = np.array([t0 + 900 * k for k in range(len(rows))], dtype=np.int64)
    a = np.array(rows, dtype=float)
    return Bars(t, a[:, 0], a[:, 1], a[:, 2], a[:, 3], np.full(len(rows), 1000.0))


def _exit_of(bars, sl, tp, p=None):
    """Drive only the IN_TRADE branch by hand: bar 0 is the entry bar."""
    p = p or Params()
    tr = E.Trade(entry_bar=0, entry_time=int(bars.t[0]), entry=100.0, sl=sl, tp=tp, risk=100.0 - sl,
                 rr=(tp - 100.0) / (100.0 - sl), sl_source="HL", tp_source="RR", tp_level=np.nan,
                 zone_kind="EMA20", zone_level=99.0, zinv=98.0, rl=98.5, hl=99.0, sh=100.0, arm_bar=0)
    for i in range(1, len(bars)):
        o, h, l, c = bars.o[i], bars.h[i], bars.l[i], bars.c[i]
        if o <= tr.sl:
            return "SL_GAP", o
        if o >= tr.tp:
            return "TP_GAP", o
        if l <= tr.sl:
            return "SL", tr.sl
        if h >= tr.tp:
            return "TP", tr.tp
    return "", np.nan


def test_stop_wins_when_both_touched_in_one_bar():
    bars = _trade_bars([(100, 100, 100, 100), (100, 110, 90, 105)])
    assert _exit_of(bars, sl=95.0, tp=105.0) == ("SL", 95.0)


def test_gap_beyond_the_level_fills_at_the_open():
    assert _exit_of(_trade_bars([(100, 100, 100, 100), (90, 95, 88, 94)]), 95.0, 105.0) == ("SL_GAP", 90.0)
    assert _exit_of(_trade_bars([(100, 100, 100, 100), (108, 110, 107, 109)]), 95.0, 105.0) == ("TP_GAP", 108.0)


def test_entry_bar_is_never_an_exit_bar():
    # The entry bar's own low is below the stop; it must not exit on bar 0.
    bars = _trade_bars([(100, 101, 90, 100), (100, 101, 99, 100)])
    assert _exit_of(bars, sl=95.0, tp=105.0) == ("", np.nan) or _exit_of(bars, 95.0, 105.0)[0] == ""


# ---------------------------------------------------------------- entry gate
class _FakeHTF:
    def __init__(self, atr1=20.0, h24=120.0, prov=np.nan, close=100.0):
        self.atr = np.array([atr1])
        self.h24 = np.array([h24])
        self.prov_high = np.array([prov])
        self.close = np.array([close])


def _gate(hl=99.0, close=100.0, atr15=2.0, ph4=(), ph1=(), p=None, z=99.0, tol=1.0, zinv=98.0, h24=120.0):
    p = p or Params()
    t = np.array([int(datetime(2026, 4, 6, 10, 0, tzinfo=ET).timestamp())])
    arr = lambda v: np.array([v], dtype=float)  # noqa: E731
    return E.entry_gate(
        0, p, arr(close), arr(close), arr(close), arr(close), t, arr(atr15),
        _FakeHTF(), _FakeHTF(h24=h24),
        0, 0, z, tol, zinv, hl,
        [E.Piv(x, 0) for x in ph4], [E.Piv(x, 0) for x in ph1],
    )


def test_gate_uses_the_higher_low_for_the_stop():
    verdict, info = _gate(hl=99.0, close=100.0, ph1=(104.0,))
    assert verdict == "ENTER"
    assert info["sl"] == 99.0 - 0.25          # 1 tick below the higher low
    assert info["sl_source"] == "HL"
    assert info["risk"] == pytest.approx(1.25)


def test_gate_falls_back_to_the_zone_floor_only_when_risk_is_below_the_floor():
    # HL one tick under the close -> risk 0.5 < max(0.5*ATR15, 4 ticks) = 1.0
    verdict, info = _gate(hl=99.75, close=100.0, atr15=2.0, zinv=98.0, ph1=(110.0,))
    assert verdict == "ENTER"
    assert info["sl_source"] == "1H-INV"
    assert info["sl"] == 98.0 - 0.25


def test_gate_skips_when_even_the_zone_floor_is_too_tight():
    verdict, info = _gate(hl=99.9, close=100.0, atr15=8.0, zinv=99.8)
    assert (verdict, info["reason"]) == ("SKIP", "RISK_FLOOR")


def test_gate_skips_when_risk_exceeds_the_cap():
    p = Params(max_risk_atr=1.0)               # cap = 1.0 x ATR1H = 20 points
    verdict, info = _gate(hl=70.0, close=100.0, p=p, ph1=(200.0,))
    assert (verdict, info["reason"]) == ("SKIP", "RISK_CAP")


def test_strong_level_inside_min_rr_skips_the_trade():
    # A 4H pivot high 1 point above entry: rr well under minRR -> that is the
    # user's "no immediate strong resistance" rule.
    verdict, info = _gate(hl=99.0, close=100.0, ph4=(101.0,))
    assert (verdict, info["reason"]) == ("SKIP", "TP_STRONG_WALL")


def test_weak_level_inside_min_rr_is_ignored_and_the_next_one_is_taken():
    verdict, info = _gate(hl=99.0, close=100.0, ph1=(100.5, 104.0))
    assert verdict == "ENTER"
    assert info["tp_source"] == "1H-PH"
    assert info["tp"] == 104.0 - 2 * 0.25


def test_the_24h_high_is_itself_a_target_candidate():
    verdict, info = _gate(hl=99.0, close=100.0, ph4=(), ph1=(), h24=120.0)
    assert (verdict, info["tp_source"]) == ("ENTER", "1H-HIGH")


def test_fallback_is_the_users_one_to_two():
    # No level above the entry at all: the 24h high is below it (the pullback
    # high was already taken out) and there are no pivot highs left.
    verdict, info = _gate(hl=99.0, close=100.0, ph4=(), ph1=(), h24=99.5)
    assert verdict == "ENTER"
    assert info["tp_source"] == "RR"
    assert info["rr"] == pytest.approx(2.0)
    assert info["tp"] == pytest.approx(100.0 + 2.0 * 1.25)


def test_entry_is_deferred_on_the_bar_closing_into_the_halt():
    p = Params()
    t = np.array([int(datetime(2026, 4, 6, 15, 45, tzinfo=CT).timestamp())])
    arr = lambda v: np.array([v], dtype=float)  # noqa: E731
    verdict, info = E.entry_gate(0, p, arr(100.0), arr(100.0), arr(100.0), arr(100.0), t, arr(2.0),
                                 _FakeHTF(), _FakeHTF(), 0, 0, 99.0, 1.0, 98.0, 99.0, [], [])
    assert (verdict, info["reason"]) == ("DEFER", "SESSION_LAST_BAR")


# ---------------------------------------------------------------- causality
@pytest.fixture(scope="module")
def sample():
    return load_csv_gz(DATA / "MNQ1_15m.csv.gz")


def test_no_rule_reads_an_unclosed_bar(sample):
    """Prefix truncation: cutting the data short must not change any earlier
    decision. A rule that peeked at a later bar would change its verdict here."""
    cut = 4200
    full = run(sample)
    part = run(sample.slice(0, cut))
    assert np.array_equal(full.state[:cut], part.state[:cut])
    assert full.block[:cut] == part.block[:cut]
    ev_full = [e for e in full.events if e["bar"] < cut]
    assert ev_full == part.events


def test_engine_produces_well_formed_trades(sample):
    res = run(sample)
    assert res.warm_ok_bar > 0
    assert len(res.trades) > 0, "the rule set produced no trades on the sample"
    for tr in res.trades:
        assert tr.sl < tr.entry < tr.tp
        assert tr.risk > 0
        assert tr.rr >= Params().min_rr - 1e-9
        for px in (tr.entry, tr.sl, tr.tp):
            assert abs(px / 0.25 - round(px / 0.25)) < 1e-9, f"{px} is off the tick grid"
        if tr.exit_bar >= 0:
            assert tr.exit_bar > tr.entry_bar


def test_only_one_position_at_a_time(sample):
    res = run(sample)
    for a, b in zip(res.trades, res.trades[1:]):
        assert a.exit_bar >= 0 and b.entry_bar > a.exit_bar


def test_higher_timeframe_values_lag_by_one_closed_bar(sample):
    """The 4H bar that closes with 15M bar i must not be visible on bar i."""
    h4 = E.build_htf(sample, 240, Params())
    for i in (500, 1500, 3000):
        ref = h4.map_idx[i] - 1
        assert h4.bars.t[ref] + 240 * 60 <= sample.t[i], "HTF reference bar had not closed"
