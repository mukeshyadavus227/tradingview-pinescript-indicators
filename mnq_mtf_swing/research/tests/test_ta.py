import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ta import atr, ema, pivots  # noqa: E402


def test_ema_seeds_with_first_value_and_matches_recursion():
    x = np.array([10.0, 11.0, 12.0, 11.0, 10.0])
    e = ema(x, 3)
    a = 0.5
    assert e[0] == 10.0
    assert abs(e[1] - (a * 11 + (1 - a) * 10)) < 1e-12
    assert abs(e[2] - (a * 12 + (1 - a) * e[1])) < 1e-12


def test_atr_is_na_until_seeded():
    h = np.array([2, 3, 4, 5, 6, 7], dtype=float)
    l = h - 1
    c = h - 0.5
    a = atr(h, l, c, 3)
    assert np.isnan(a[0]) and np.isnan(a[1])
    # TR is 1.0 everywhere except bar>0 where |h-pc| = 1.5 dominates.
    assert abs(a[2] - np.mean([1.0, 1.5, 1.5])) < 1e-12


def test_pivot_high_confirmation_and_tie_rules():
    #            0   1   2   3   4   5   6   7
    high = np.array([1, 2, 5, 3, 2, 5, 4, 1], dtype=float)
    low = high - 1
    ph, pl, ph_idx, pl_idx = pivots(high, low, left=2, right=2)
    # bar 2 (5) is strictly above bars 0,1 and >= bars 3,4 -> pivot, confirmed on bar 4
    assert ph_idx[4] == 2 and ph[4] == 5
    # bar 5 (5): left window is bars 3,4 (3,2) -> strictly above; right bars 6,7 (4,1) -> pivot on bar 7
    assert ph_idx[7] == 5 and ph[7] == 5
    # nothing confirmed on other bars
    assert set(np.flatnonzero(~np.isnan(ph))) == {4, 7}


def test_pivot_high_right_tie_is_allowed_left_tie_is_not():
    #            0   1   2   3   4   5
    high = np.array([1, 5, 5, 2, 1, 1], dtype=float)
    low = high - 1
    ph, _, ph_idx, _ = pivots(high, low, left=1, right=2)
    # bar 1: left bar 0 (1) strictly below, right bars 2,3 (5,2) -> 5 >= 5 ok -> pivot confirmed on bar 3
    assert ph_idx[3] == 1
    # bar 2: left bar 1 equals 5 -> NOT strictly above -> not a pivot (no double count)
    assert ph_idx[4] == -1


def test_pivot_low_mirror():
    low = np.array([5, 4, 1, 3, 4, 1, 2, 5], dtype=float)
    high = low + 1
    _, pl, _, pl_idx = pivots(high, low, left=2, right=2)
    assert pl_idx[4] == 2 and pl[4] == 1
    assert pl_idx[7] == 5


def test_pivots_are_causal():
    rng = np.random.default_rng(1)
    high = np.cumsum(rng.normal(size=300)) + 100
    low = high - rng.uniform(0.5, 2.0, size=300)
    full = pivots(high, low, 3, 3)
    cut = 200
    part = pivots(high[:cut], low[:cut], 3, 3)
    for a, b in zip(full, part):
        assert np.array_equal(np.nan_to_num(a[:cut], nan=-999), np.nan_to_num(b, nan=-999))
