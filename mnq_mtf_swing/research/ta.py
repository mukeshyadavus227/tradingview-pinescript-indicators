"""
Indicator primitives shared by the Python mirror, with the same semantics the
Pine indicator implements. ema/rma/atr follow Pine's ta.* seeding rules
(copied from adaptive_scanner/research/pine_ta.py, same author, same licence).

The pivot function is NOT ta.pivothigh/ta.pivotlow. Tie handling of the native
functions is undocumented, so mnq_mtf_swing.pine ships its own f_pivot_high /
f_pivot_low with this exact definition, and the mirror implements the same one:

    bar p is a pivot HIGH with strength (L, R) iff
        high[p] >  high[p-k]  for every k in 1..L   (strictly above the left)
        high[p] >= high[p+k]  for every k in 1..R   (at or above the right)
    and it is CONFIRMED on bar p + R (the first bar on which it is knowable).

    pivot LOW is the mirror image (strictly below the left, at or below the right).

A bar that ties the centre on the right is therefore not itself a pivot later
(its own left window contains the equal centre), so no level is double-counted.

Conventions: numpy float arrays, nan = Pine na, index 0 = oldest bar.
"""
from __future__ import annotations

import numpy as np

NAN = np.nan


def ema(x, n: int):
    """Pine ta.ema: alpha = 2/(n+1); seeded with the first non-na source value."""
    x = np.asarray(x, dtype=float)
    a = 2.0 / (n + 1.0)
    out = np.full(len(x), NAN)
    prev = NAN
    for i, v in enumerate(x):
        if np.isnan(v):
            out[i] = prev
            continue
        prev = v if np.isnan(prev) else a * v + (1 - a) * prev
        out[i] = prev
    return out


def sma(x, n: int):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), NAN)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1 : i + 1]
        if not np.isnan(w).any():
            out[i] = w.mean()
    return out


def rma(x, n: int):
    """Pine ta.rma: alpha = 1/n; seeded with ta.sma(x, n) at the first bar where that is not na."""
    x = np.asarray(x, dtype=float)
    seed = sma(x, n)
    a = 1.0 / n
    out = np.full(len(x), NAN)
    prev = NAN
    for i, v in enumerate(x):
        if np.isnan(prev):
            if not np.isnan(seed[i]):
                prev = seed[i]
                out[i] = prev
            continue
        prev = a * (0.0 if np.isnan(v) else v) + (1 - a) * prev
        out[i] = prev
    return out


def true_range(h, l, c):
    """Pine ta.tr(true): high-low on the first bar."""
    h = np.asarray(h, dtype=float)
    l = np.asarray(l, dtype=float)
    c = np.asarray(c, dtype=float)
    pc = np.r_[NAN, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    tr[0] = h[0] - l[0]
    return tr


def atr(h, l, c, n: int):
    return rma(true_range(h, l, c), n)


def pivots(high, low, left: int, right: int):
    """Confirmed swing pivots.

    Returns (ph, pl, ph_idx, pl_idx): arrays indexed by the CONFIRMATION bar.
    ph[i] is the pivot-high price confirmed on bar i (its bar is i-right), else
    nan; ph_idx[i] is that bar's index (or -1). Same for lows.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    ph = np.full(n, NAN)
    pl = np.full(n, NAN)
    ph_idx = np.full(n, -1, dtype=int)
    pl_idx = np.full(n, -1, dtype=int)
    for i in range(left + right, n):
        p = i - right
        hp = high[p]
        lp = low[p]
        is_high = True
        is_low = True
        for k in range(1, left + 1):
            if not (hp > high[p - k]):
                is_high = False
            if not (lp < low[p - k]):
                is_low = False
            if not is_high and not is_low:
                break
        if is_high or is_low:
            for k in range(1, right + 1):
                if is_high and not (hp >= high[p + k]):
                    is_high = False
                if is_low and not (lp <= low[p + k]):
                    is_low = False
                if not is_high and not is_low:
                    break
        if is_high:
            ph[i] = hp
            ph_idx[i] = p
        if is_low:
            pl[i] = lp
            pl_idx[i] = p
    return ph, pl, ph_idx, pl_idx
