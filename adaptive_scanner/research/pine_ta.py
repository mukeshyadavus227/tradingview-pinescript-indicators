"""
Exact re-implementations of the Pine Script `ta.*` functions used by
asr_engine.pine, on numpy arrays. Every seeding and na-handling rule below is
the one Pine actually uses; parity with the Strategy Tester depends on it.

Conventions: arrays are float64, `nan` is Pine `na`, index 0 is the oldest bar.
"""
import numpy as np

NAN = np.nan


def shift(x, n=1):
    """Pine `x[n]` — value n bars ago, na for the first n bars."""
    out = np.full_like(x, NAN, dtype=float)
    if n < len(x):
        out[n:] = x[:-n] if n > 0 else x
    return out


def change(x):
    return x - shift(x, 1)


def sma(x, n):
    """Pine ta.sma: na until n bars are available; na if any value in the window is na."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), NAN)
    if len(x) < n:
        return out
    isn = np.isnan(x)
    c = np.cumsum(np.where(isn, 0.0, x))
    cn = np.cumsum(isn.astype(int))
    for i in range(n - 1, len(x)):
        lo = i - n + 1
        nn = cn[i] - (cn[lo - 1] if lo > 0 else 0)
        if nn == 0:
            s = c[i] - (c[lo - 1] if lo > 0 else 0.0)
            out[i] = s / n
    return out


def rolling_sum(x, n):
    """Pine math.sum: same na semantics as sma, without the division."""
    s = sma(x, n)
    return s * n


def ema(x, n):
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


def rma(x, n):
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
        # Pine: alpha * src + (1 - alpha) * nz(sum[1])
        prev = a * (0.0 if np.isnan(v) else v) + (1 - a) * prev
        out[i] = prev
    return out


def rsi(x, n):
    ch = change(x)
    u = np.where(np.isnan(ch), NAN, np.maximum(ch, 0.0))
    d = np.where(np.isnan(ch), NAN, np.maximum(-ch, 0.0))
    ru, rd = rma(u, n), rma(d, n)
    out = np.full(len(x), NAN)
    for i in range(len(x)):
        if np.isnan(ru[i]) or np.isnan(rd[i]):
            continue
        if rd[i] == 0:
            out[i] = 100.0
        elif ru[i] == 0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ru[i] / rd[i])
    return out


def true_range(h, l, c, handle_na):
    """Pine ta.tr(handle_na). handle_na=false is the `ta.tr` variable (na on bar 0)."""
    pc = shift(c, 1)
    hl = h - l
    out = np.maximum.reduce([hl, np.abs(h - pc), np.abs(l - pc)])
    first = np.isnan(pc)
    out[first] = hl[first] if handle_na else NAN
    return out


def atr(h, l, c, n):
    return rma(true_range(h, l, c, True), n)


def fixnan(x):
    out = np.asarray(x, dtype=float).copy()
    last = NAN
    for i in range(len(out)):
        if np.isnan(out[i]):
            out[i] = last
        else:
            last = out[i]
    return out


def dmi(h, l, c, di_len, adx_len):
    """Pine ta.dmi → (plus, minus, adx). Source transcribed from the Pine reference implementation."""
    up = change(h)
    down = -change(l)
    plus_dm = np.where(np.isnan(up), NAN, np.where((up > down) & (up > 0), up, 0.0))
    minus_dm = np.where(np.isnan(down), NAN, np.where((down > up) & (down > 0), down, 0.0))
    trur = rma(true_range(h, l, c, False), di_len)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus = fixnan(100.0 * rma(plus_dm, di_len) / trur)
        minus = fixnan(100.0 * rma(minus_dm, di_len) / trur)
    s = plus + minus
    dx = np.abs(plus - minus) / np.where(s == 0, 1.0, s)
    adx = 100.0 * rma(dx, adx_len)
    return plus, minus, adx


def stdev(x, n):
    """Pine ta.stdev(src, n) — biased (population) by default."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), NAN)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1 : i + 1]
        if np.isnan(w).any():
            continue
        out[i] = np.sqrt(np.mean((w - w.mean()) ** 2))
    return out


def bb(x, n, mult):
    basis = sma(x, n)
    dev = mult * stdev(x, n)
    return basis, basis + dev, basis - dev


def macd(x, f, s, sig):
    m = ema(x, f) - ema(x, s)
    sg = ema(m, sig)
    return m, sg, m - sg


def highest(x, n):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), NAN)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1 : i + 1]
        if not np.isnan(w).any():
            out[i] = w.max()
    return out


def lowest(x, n):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), NAN)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1 : i + 1]
        if not np.isnan(w).any():
            out[i] = w.min()
    return out


def vwma(c, v, n):
    return sma(c * v, n) / sma(v, n)


def crossover(a, b):
    a1, b1 = shift(a, 1), shift(b, 1)
    with np.errstate(invalid="ignore"):
        return (a > b) & (a1 <= b1)


def crossunder(a, b):
    a1, b1 = shift(a, 1), shift(b, 1)
    with np.errstate(invalid="ignore"):
        return (a < b) & (a1 >= b1)


def barssince(cond):
    """Pine ta.barssince: bars since cond was last true (0 on that bar); na if never."""
    out = np.full(len(cond), NAN)
    last = -1
    for i, c in enumerate(cond):
        if c:
            last = i
        if last >= 0:
            out[i] = i - last
    return out


def nz(x, repl=0.0):
    x = np.asarray(x, dtype=float)
    return np.where(np.isnan(x), repl, x)


def pine_round(x):
    """Pine math.round: half away from zero (numpy rounds half to even)."""
    x = np.asarray(x, dtype=float)
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def round_to_mintick(x, mintick=0.01):
    return pine_round(np.asarray(x, dtype=float) / mintick) * mintick
