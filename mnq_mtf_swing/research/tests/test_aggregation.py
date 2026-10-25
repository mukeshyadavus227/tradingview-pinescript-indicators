"""
The 1H and 4H bars the Sierra Chart study aggregates from 15M bars must be the
bars TradingView serves for request.security("60"/"240"), otherwise the two
platforms trade different structures. This test checks that on the committed
MNQ sample: every aggregated bar whose 15M coverage is complete must match the
TradingView bar with the same open time exactly (OHLC to the tick, volume to
the contract).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from bars import ET, aggregate, htf_open_time, load_csv_gz, session_anchor_utc  # noqa: E402

DATA = HERE.parent / "data"


@pytest.fixture(scope="module")
def m15():
    return load_csv_gz(DATA / "MNQ1_15m.csv.gz")


@pytest.mark.parametrize("htf_minutes,fname", [(60, "MNQ1_1h.csv.gz"), (240, "MNQ1_4h.csv.gz")])
def test_aggregated_bars_match_tradingview(m15, htf_minutes, fname):
    tv = load_csv_gz(DATA / fname)
    agg, map_idx = aggregate(m15, htf_minutes)
    tv_by_t = {int(t): i for i, t in enumerate(tv.t)}

    checked = 0
    mismatches = []
    for j in range(len(agg)):
        t = int(agg.t[j])
        # Coverage: the aggregated bar must start at the same time as the first
        # 15M bar it contains (otherwise the sample simply starts mid-bar) and
        # must not be the sample's last (still forming) bar.
        first_lower = int(m15.t[np.flatnonzero(map_idx == j)[0]])
        if first_lower != t or j == len(agg) - 1:
            continue
        i = tv_by_t.get(t)
        if i is None:
            mismatches.append((t, "missing in TradingView file"))
            continue
        checked += 1
        for name, a, b in (("o", agg.o[j], tv.o[i]), ("h", agg.h[j], tv.h[i]), ("l", agg.l[j], tv.l[i]), ("c", agg.c[j], tv.c[i])):
            if abs(a - b) > 1e-9:
                mismatches.append((t, f"{name}: agg {a} vs tv {b}"))
        if abs(agg.v[j] - tv.v[i]) > 0.5:
            mismatches.append((t, f"v: agg {agg.v[j]} vs tv {tv.v[i]}"))
    assert checked > 100, f"too few complete bars checked: {checked}"
    # The very last TradingView bars were still forming at fetch time (see
    # data/README.md); tolerate mismatches only there.
    last_t = int(tv.t[-1])
    real = [m for m in mismatches if m[0] < last_t - 2 * htf_minutes * 60]
    assert not real, f"{len(real)} mismatching {htf_minutes}m bars out of {checked}; first: {real[:5]}"


def test_4h_anchor_is_18_et_across_dst():
    # US DST changes on Sunday 2026-03-08 02:00 and Sunday 2026-11-01 02:00,
    # both inside the weekend closure (Fri 17:00 -> Sun 18:00 ET), so no
    # session ever spans a change. The first session after each change must
    # still open its 4h bars at 18/22/02/06/10/14 ET wall time, which is what
    # the committed TradingView 4h file shows.
    import datetime as dt

    def et(y, mo, d, hh, mm):
        return int(dt.datetime(y, mo, d, hh, mm, tzinfo=ET).timestamp())

    # Friday before spring-forward (EST): last bar of the week opens 14:00.
    assert htf_open_time(et(2026, 3, 6, 16, 59), 240) == et(2026, 3, 6, 14, 0)
    # Sunday/Monday after spring-forward (EDT).
    assert htf_open_time(et(2026, 3, 8, 18, 0), 240) == et(2026, 3, 8, 18, 0)
    assert htf_open_time(et(2026, 3, 8, 21, 59), 240) == et(2026, 3, 8, 18, 0)
    assert htf_open_time(et(2026, 3, 9, 3, 30), 240) == et(2026, 3, 9, 2, 0)
    assert htf_open_time(et(2026, 3, 9, 16, 59), 240) == et(2026, 3, 9, 14, 0)
    # Monday after fall-back (EST): anchor is Sunday 18:00 EST.
    assert session_anchor_utc(et(2026, 11, 2, 17, 0)) == et(2026, 11, 1, 18, 0)
    assert htf_open_time(et(2026, 11, 2, 9, 45), 240) == et(2026, 11, 2, 6, 0)
    # The 15M bar opening at 17:59 ET belongs to the 14:00 bar (session ends 17:00, no bars exist here, but the mapping must be monotone).
    assert htf_open_time(et(2026, 3, 9, 17, 59), 240) == et(2026, 3, 9, 14, 0)


def test_map_idx_points_to_containing_bar(m15):
    agg, map_idx = aggregate(m15, 60)
    assert len(map_idx) == len(m15)
    assert np.all(np.diff(map_idx) >= 0)
    for i in (0, 17, 1000, len(m15) - 1):
        j = map_idx[i]
        assert agg.t[j] <= m15.t[i] < agg.t[j] + 3600
