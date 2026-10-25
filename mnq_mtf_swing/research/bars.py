"""
Bar loading and higher-timeframe aggregation for the MNQ MTF swing engine.

The Sierra Chart study builds its 1H and 4H bars from the chart's own 15M bars
(one chart, no cross-chart references). The Pine indicator gets them from
request.security(). Both must see the SAME bars, so the aggregation rule is
pinned here and tested against TradingView's own 1h/4h bars in
tests/test_aggregation.py:

    A higher-timeframe bar of N minutes opens at the session anchor
    (18:00 America/New_York, the CME Globex open) plus k*N minutes, k >= 0,
    and contains every 15M bar whose OPEN time falls in [open, open + N).

The anchor is expressed in exchange-local wall time so it does not move across
DST changes (TradingView's 4h bars open at 18/22/02/06/10/14 ET all year; the
UTC anchor shifts by an hour in March and November).

Timestamps everywhere are bar OPEN times in Unix seconds (UTC), as in the CSVs.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
SESSION_ANCHOR_MINUTES = 18 * 60  # 18:00 exchange-local wall time


@dataclass
class Bars:
    """Column arrays. `t` is the bar open time (Unix seconds, UTC)."""

    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray

    def __len__(self) -> int:
        return len(self.t)

    def slice(self, start: int, stop: int) -> "Bars":
        return Bars(*(a[start:stop] for a in (self.t, self.o, self.h, self.l, self.c, self.v)))


def load_csv_gz(path: str | Path) -> Bars:
    """Read a `t,o,h,l,c,v` gzipped CSV (bar open times, ascending)."""
    with gzip.open(path, "rt") as fh:
        header = fh.readline().strip().split(",")
        assert header == ["t", "o", "h", "l", "c", "v"], header
        rows = [line.rstrip("\n").split(",") for line in fh if line.strip()]
    arr = np.array(rows, dtype=float)
    t = arr[:, 0].astype(np.int64)
    assert np.all(np.diff(t) > 0), "timestamps must be strictly increasing"
    return Bars(t, arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4], arr[:, 5])


def session_anchor_utc(t_unix: int, anchor_minutes: int = SESSION_ANCHOR_MINUTES, tz: ZoneInfo = ET) -> int:
    """Unix time of the most recent session anchor (18:00 ET) at or before t."""
    local = datetime.fromtimestamp(int(t_unix), tz)
    anchor = local.replace(hour=anchor_minutes // 60, minute=anchor_minutes % 60, second=0, microsecond=0)
    if anchor > local:
        anchor = (local - timedelta(days=1)).replace(
            hour=anchor_minutes // 60, minute=anchor_minutes % 60, second=0, microsecond=0
        )
    # Re-resolve through the zone so a DST transition between the two wall
    # times yields the correct UTC instant.
    anchor = datetime(anchor.year, anchor.month, anchor.day, anchor.hour, anchor.minute, tzinfo=tz)
    return int(anchor.timestamp())


def htf_open_time(t_unix: int, htf_minutes: int, anchor_minutes: int = SESSION_ANCHOR_MINUTES) -> int:
    """Open time of the N-minute higher-timeframe bar containing the bar that opens at t."""
    a = session_anchor_utc(t_unix, anchor_minutes)
    k = (int(t_unix) - a) // (htf_minutes * 60)
    return a + k * htf_minutes * 60


def aggregate(bars: Bars, htf_minutes: int, anchor_minutes: int = SESSION_ANCHOR_MINUTES):
    """Aggregate lower-timeframe bars into N-minute bars anchored at the session open.

    Returns (htf_bars, map_idx) where map_idx[i] is the index of the HTF bar
    that CONTAINS lower-timeframe bar i (the forming bar from bar i's point of
    view). The last CLOSED HTF bar as of lower bar i is therefore map_idx[i]-1,
    and a rule that must not look ahead reads HTF values at map_idx[i]-1 only.
    """
    n = len(bars)
    opens = np.fromiter((htf_open_time(int(t), htf_minutes, anchor_minutes) for t in bars.t), dtype=np.int64, count=n)
    # New HTF bar whenever the containing open time changes (bars are ascending).
    starts = np.flatnonzero(np.r_[True, opens[1:] != opens[:-1]])
    ends = np.r_[starts[1:], n]
    m = len(starts)
    t = opens[starts]
    o = bars.o[starts]
    c = bars.c[ends - 1]
    h = np.empty(m)
    l = np.empty(m)
    v = np.empty(m)
    for j, (s, e) in enumerate(zip(starts, ends)):
        h[j] = bars.h[s:e].max()
        l[j] = bars.l[s:e].min()
        v[j] = bars.v[s:e].sum()
    map_idx = np.repeat(np.arange(m), ends - starts)
    return Bars(t, o, h, l, c, v), map_idx


def iso(t_unix: int) -> str:
    return datetime.fromtimestamp(int(t_unix), timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
