"""
Python mirror of asr_engine.pine on a DAILY chart.

Every block below is named for the Pine block it mirrors and follows the same
evaluation order. Where the Pine takes a higher-timeframe context via
request.security(..., expr[1], lookahead_on), the mirror reproduces exactly
what that resolves to: on a 1D chart the daily context is the chart's own
series shifted by one bar, and the weekly context on any day of week k is the
completed value of week k-1.

Parity is verified separately (parity_test.py) against the Strategy Tester's
trade list. Until that passes, treat this mirror as "faithful by construction",
not "proven".
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
import pine_ta as ta

NAN = np.nan
ET = "America/New_York"


@dataclass(frozen=True)
class Profile:
    name: str
    min_score: float
    cooldown_min: int
    min_rr: float
    atr_stop_mult: float
    time_stop_days: int


SWING = Profile("SWING", 75.0, 7200, 1.5, 1.5, 15)
POSITIONAL = Profile("POSITIONAL", 70.0, 21600, 1.5, 2.75, 60)
PROFILES = {"SWING": SWING, "POSITIONAL": POSITIONAL}


@dataclass(frozen=True)
class Params:
    """Pine input defaults. Field names follow the Pine identifiers."""
    adxLen: int = 14
    adxTrendThr: int = 25
    adxRangeThr: int = 20
    chopLen: int = 14
    bbwLen: int = 20
    bbwStd: float = 2.0
    s1_rsiLen: int = 14
    s1_oversold: int = 30
    s1_overbought: int = 70
    s1_supportLen: int = 20
    s2_entryLen: int = 20
    s2_trendSMA: int = 50
    s2_volMult: float = 1.3
    s3_fastEMA: int = 9
    s3_slowEMA: int = 21
    s3_trendEMA: int = 50
    s3_macdFast: int = 12
    s3_macdSlow: int = 26
    s3_macdSig: int = 9
    s3_crossMax: int = 5
    s4_wkFast: int = 20
    s4_wkSlow: int = 50
    s4_dailyEMA: int = 21
    s4_rsiPBLo: int = 40
    s4_rsiPBHi: int = 60
    atrLen: int = 14
    minDollarVol: float = 5.0
    minPrice: float = 5.0
    shortEnabled: bool = False
    useRegimeFilter: bool = True
    mintick: float = 0.01
    # ── v3 rules (Phase 3). version="v2" reproduces the Phase 1/2 engine exactly. ──
    version: str = "v2"
    s1_enabled: bool = True       # v3: S1 is SWING-only (loses with POSITIONAL's wide stops)
    s1_trendGate: int = 18        # v3: S1 fires on trigger AND trend component >= this; no regime gate, no min score
    s2_enabled: bool = True       # v3: False — no edge
    s3_useThreshold: bool = True  # v3: gate S3 at s3_gate — not a predictor, a slot-cap rate limiter
    s3_gate: float = 70.0
    s4_minScore: float = 75.0     # v3: S4 keeps its validated threshold regardless of profile min score
    priority: tuple = (1, 4, 3, 2)  # v3: winner = highest-priority eligible strategy (validated expectancy order), not max score


V3_PARAMS = None  # set below


DEFAULT_PARAMS = Params()
V3_PARAMS = Params(version="v3", useRegimeFilter=False, s2_enabled=False, s3_useThreshold=False)
# Deployed v3 (mirrors asr_engine.pine defaults): SWING = S1 + S4 + S3 gated at 70; POSITIONAL = S4 only.
V3_SWING = Params(version="v3", useRegimeFilter=False, s2_enabled=False, s3_useThreshold=True, s3_gate=70.0, s1_enabled=True)
V3_POSITIONAL = Params(version="v3", useRegimeFilter=False, s2_enabled=False, s1_enabled=False, priority=(4,))
V3_DEPLOYED = {"SWING": V3_SWING, "POSITIONAL": V3_POSITIONAL}


# ────────────────────────────────────────────────────────────────────────────
# Daily context  (Pine f_ctx with bpy = 252, evaluated one bar back)
# ────────────────────────────────────────────────────────────────────────────
def daily_context(o, h, l, c, v, bpy=252):
    nAtr = max(2, int(ta.pine_round(bpy / 18.0)))
    nAdv = max(2, int(ta.pine_round(bpy / 12.6)))
    n50 = max(2, int(ta.pine_round(bpy / 5.04)))
    n200 = max(2, int(ta.pine_round(bpy / 1.26)))
    n1m = max(1, int(ta.pine_round(bpy / 12.6)))
    n3m = max(1, int(ta.pine_round(bpy / 4.2)))
    n6m = max(1, int(ta.pine_round(bpy / 2.0)))
    n12m = max(2, bpy)

    _atr = ta.atr(h, l, c, nAtr)
    _rsi = ta.rsi(c, 14)
    _, _, _adx = ta.dmi(h, l, c, 14, 14)
    _s50 = ta.sma(c, n50)
    _s200 = ta.sma(c, n200)
    _adv = ta.sma(v, nAdv) * c
    _hi = ta.highest(h, n12m)
    _lo = ta.lowest(l, n12m)

    def roc(n):
        p = ta.shift(c, n)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(p > 0, (c - p) / p * 100.0, NAN)

    _r1, _r2, _r3 = roc(n1m), roc(n3m), roc(n6m)
    p12, p1 = ta.shift(c, n12m), ta.shift(c, n1m)
    with np.errstate(invalid="ignore", divide="ignore"):
        _m121 = np.where((p12 > 0) & ~np.isnan(p1), (p1 / p12 - 1.0) * 100.0, NAN)

    # [F4] ATR percentile of the PREVIOUS bar's ATR against the n12m bars before it.
    n = len(c)
    _atrP = np.full(n, NAN)
    _atrPrev = ta.shift(_atr, 1)
    for t in range(n):
        if np.isnan(_atrPrev[t]):
            continue
        seen = cnt = 0
        for i in range(2, n12m + 2):
            if t - i < 0:
                break
            a = _atr[t - i]
            if not np.isnan(a):
                seen += 1
                if _atrPrev[t] > a:
                    cnt += 1
        if seen >= 20:
            _atrP[t] = cnt / seen * 100.0

    pc = ta.shift(c, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        _gap = np.where(pc > 0, (o - pc) / pc * 100.0, NAN)
    _gapA = ta.sma(np.abs(ta.nz(_gap)), nAdv)
    bar_index = np.arange(n, dtype=float)

    s = ta.shift  # every element at offset [1]  ([F5]); _atrP is already one bar back
    return dict(
        dAtr=s(_atr), dAtrPct=_atrP, dAdvUsd=s(_adv), dHi52=s(_hi), dLo52=s(_lo),
        dRoc20=s(_r1), dRoc60=s(_r2), dRoc126=s(_r3), dMom121=s(_m121),
        dSma50=s(_s50), dSma200=s(_s200), dRsi=s(_rsi), dAdx=s(_adx), dGapAvg=s(_gapA),
        dCtxBars=s(bar_index),
    )


# ────────────────────────────────────────────────────────────────────────────
# Weekly context  (Pine f_wk via request.security("W", expr[1], lookahead_on))
# ────────────────────────────────────────────────────────────────────────────
def weekly_context(dates_et, o, h, l, c, wkFast, wkSlow):
    iso = dates_et.isocalendar()
    key = iso.year.astype(int) * 100 + iso.week.astype(int)
    df = pd.DataFrame({"k": key.values, "o": o, "h": h, "l": l, "c": c})
    wk = df.groupby("k", sort=True).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
    wf = ta.ema(wk.c.values, wkFast)
    ws = ta.ema(wk.c.values, wkSlow)
    _, _, wadx = ta.dmi(wk.h.values, wk.l.values, wk.c.values, 14, 14)
    # On any daily bar of week k, the context is week k-1's COMPLETED values.
    prev = pd.DataFrame({"wkF": ta.shift(wf, 1), "wkS": ta.shift(ws, 1),
                         "wkC": ta.shift(wk.c.values, 1), "wkADX": ta.shift(wadx, 1)}, index=wk.index)
    m = prev.reindex(df.k.values)
    return dict(s4_wkF=m.wkF.values, s4_wkS=m.wkS.values, s4_wkC=m.wkC.values, s4_wkADX=m.wkADX.values)


# ────────────────────────────────────────────────────────────────────────────
# Rubric helper
# ────────────────────────────────────────────────────────────────────────────
def rubric(trig, trend, mom, loc, vol, htf):
    z = lambda a: np.maximum(0.0, ta.nz(a))
    total = np.minimum(100.0, z(trend) + z(mom) + z(loc) + z(vol) + z(htf))
    return np.where(trig, total, 0.0)


def rubric_parts(trig, trend, mom, loc, vol, htf):
    """Same as rubric() but returns (score, components) — components are the
    un-gated values so the ablation can re-score events without a component."""
    z = lambda a: np.maximum(0.0, ta.nz(a))
    parts = np.stack([z(trend), z(mom), z(loc), z(vol), z(htf)], axis=1)
    total = np.minimum(100.0, parts.sum(axis=1))
    return np.where(trig, total, 0.0), parts


def W(cond, yes, no=0.0):
    """Pine `cond ? yes : no` with na-safe boolean."""
    return np.where(np.nan_to_num(cond.astype(float), nan=0.0) > 0, yes, no)


# ────────────────────────────────────────────────────────────────────────────
# The engine
# ────────────────────────────────────────────────────────────────────────────
def run_engine(bars: pd.DataFrame, profile: Profile = SWING, p: Params = DEFAULT_PARAMS) -> pd.DataFrame:
    """bars: columns t (unix s), o, h, l, c, v — daily. Returns a frame with every intermediate the Pine computes."""
    o, h, l, c, v = (bars[k].values.astype(float) for k in "ohlcv")
    n = len(c)
    time_ms = bars.t.values.astype(np.int64) * 1000
    dates_et = pd.to_datetime(bars.t.values, unit="s", utc=True).tz_convert(ET)

    ctx = daily_context(o, h, l, c, v)
    wk = weekly_context(dates_et, o, h, l, c, p.s4_wkFast, p.s4_wkSlow)
    R = dict(ctx); R.update(wk)

    dRange52 = ta.nz(R["dHi52"]) - ta.nz(R["dLo52"])
    with np.errstate(invalid="ignore", divide="ignore"):
        distFromHi = np.where(dRange52 > 0, (R["dHi52"] - c) / dRange52 * 100.0, NAN)
        distFromLo = np.where(dRange52 > 0, (c - R["dLo52"]) / dRange52 * 100.0, NAN)

    # ── chart-timeframe calculations ──
    atr = ta.atr(h, l, c, p.atrLen)
    diPlus, diMinus, adxVal = ta.dmi(h, l, c, p.adxLen, p.adxLen)
    rsi14 = ta.rsi(c, 14)
    volSMA20 = ta.sma(v, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        relVol = np.where(volSMA20 > 0, v / volSMA20, NAN)
    rvPctile = np.full(n, NAN)
    for t in range(n):
        if np.isnan(relVol[t]):
            continue
        seen = cnt = 0
        for i in range(1, 51):
            if t - i < 0:
                break
            vs = volSMA20[t - i]
            if not np.isnan(vs) and vs > 0:
                seen += 1
                if relVol[t] > v[t - i] / vs:
                    cnt += 1
        if seen >= 20:
            rvPctile[t] = cnt / seen * 100.0
    volAboveAvg = ~np.isnan(volSMA20) & (v > volSMA20 * 1.15)

    # ── regime detection ──
    chopATR = ta.rolling_sum(ta.true_range(h, l, c, False), p.chopLen)
    chopHL = ta.highest(h, p.chopLen) - ta.lowest(l, p.chopLen)
    with np.errstate(invalid="ignore", divide="ignore"):
        chop = np.where(chopHL > 0, 100.0 * np.log10(chopATR / chopHL) / np.log10(p.chopLen), NAN)
    bbMid, bbUp, bbLo = ta.bb(c, p.bbwLen, p.bbwStd)
    with np.errstate(invalid="ignore", divide="ignore"):
        bbw = np.where(bbMid != 0, (bbUp - bbLo) / bbMid * 100.0, NAN)
    bbwSMA = ta.sma(bbw, 50)
    bbwExpanding = ~np.isnan(bbwSMA) & (bbw > bbwSMA * 1.1)
    bbwContracting = ~np.isnan(bbwSMA) & (bbw < bbwSMA * 0.9)
    atrSMA50 = ta.sma(atr, 50)
    atrExpanding = ~np.isnan(atrSMA50) & (atr > atrSMA50 * 1.2)

    cChop = ta.nz(chop, 50.0)
    A = ta.nz(adxVal)  # Pine comparisons with na are false; nz(0) gives the same branch outcomes here
    trendScore = np.minimum(W(adxVal > p.adxTrendThr, (A - p.adxTrendThr) / 15.0) +
                            W(cChop < 38.2, (38.2 - cChop) / 20.0), 1.0) * 100.0
    breakoutScore = np.minimum(W(atrExpanding, 0.4) + W(bbwExpanding, 0.4) + W(adxVal > p.adxRangeThr, 0.2), 1.0) * 100.0
    meanRevScore = np.minimum(W(adxVal < p.adxRangeThr, (p.adxRangeThr - A) / 10.0) +
                              W(cChop > 61.8, (cChop - 61.8) / 20.0) + W(bbwContracting, 0.3), 1.0) * 100.0
    momentumScore = np.minimum(W((adxVal > p.adxRangeThr) & (adxVal <= p.adxTrendThr), 0.5) +
                               W(~bbwContracting & ~bbwExpanding, 0.3) +
                               W(np.abs(ta.nz(R["dRoc20"])) > 3.0, 0.2), 1.0) * 100.0
    regimeTrend = trendScore >= 60
    regimeBreakout = breakoutScore >= 60
    regimeMeanRev = meanRevScore >= 60
    regimeMomentum = (momentumScore >= 55) & ~regimeBreakout & ~regimeTrend & ~regimeMeanRev
    regime = np.where(regimeBreakout, 2, np.where(regimeTrend, 4, np.where(regimeMomentum, 3, np.where(regimeMeanRev, 1, 0))))
    regimeConf = np.select([regime == 1, regime == 2, regime == 3, regime == 4],
                           [meanRevScore, breakoutScore, momentumScore, trendScore], 0.0)

    # ── shared building blocks ──
    dSma50, dSma200 = R["dSma50"], R["dSma200"]
    aboveLT = ~np.isnan(dSma200) & (c > dSma200)
    belowLT = ~np.isnan(dSma200) & (c < dSma200)
    ltUp = ~np.isnan(dSma50) & ~np.isnan(dSma200) & (dSma50 > dSma200)
    ltDn = ~np.isnan(dSma50) & ~np.isnan(dSma200) & (dSma50 < dSma200)
    volScore = W(volAboveAvg, 10.0) + W(ta.nz(rvPctile, 50.0) > 70.0, 5.0)
    dAtrPct = R["dAtrPct"]
    atrSane = ~np.isnan(dAtrPct) & (dAtrPct >= 15.0) & (dAtrPct <= 85.0)
    R0 = regime == 0

    # ── S1 ──
    s1_rsi = ta.rsi(c, p.s1_rsiLen)
    s1_nearSupp = (c - ta.lowest(l, p.s1_supportLen)) < atr * 1.5
    s1_nearResist = (ta.highest(h, p.s1_supportLen) - c) < atr * 1.5
    s1_trigL = (s1_rsi < p.s1_oversold) & s1_nearSupp
    s1_trigS = (s1_rsi > p.s1_overbought) & s1_nearResist
    dfh, dfl = ta.nz(distFromHi, 50.0), ta.nz(distFromLo, 50.0)
    s1_scoreLong, s1_parts = rubric_parts(s1_trigL,
        np.select([aboveLT & ltUp, aboveLT, ~np.isnan(dSma50) & (c > dSma50)], [25.0, 18.0, 10.0], 0.0),
        np.select([s1_rsi < p.s1_oversold - 10, s1_rsi < p.s1_oversold - 5], [25.0, 20.0], 14.0),
        np.select([dfh > 50.0, dfh > 30.0], [12.0, 7.0], 3.0) + W(atrSane, 8.0),
        volScore, np.select([regimeMeanRev, R0], [15.0, 8.0], 0.0))
    s1_scoreShort = rubric(s1_trigS,
        np.select([belowLT & ltDn, belowLT, ~np.isnan(dSma50) & (c < dSma50)], [25.0, 18.0, 10.0], 0.0),
        np.select([s1_rsi > p.s1_overbought + 10, s1_rsi > p.s1_overbought + 5], [25.0, 20.0], 14.0),
        np.select([dfl > 50.0, dfl > 30.0], [12.0, 7.0], 3.0) + W(atrSane, 8.0),
        volScore, np.select([regimeMeanRev, R0], [15.0, 8.0], 0.0))

    # ── S2 ──
    s2_entryHigh = ta.highest(h, p.s2_entryLen)
    s2_entryLow = ta.lowest(l, p.s2_entryLen)
    s2_sma = ta.sma(c, p.s2_trendSMA)
    s2_volSpike = ~np.isnan(volSMA20) & (v > volSMA20 * p.s2_volMult)
    eh1, el1 = ta.shift(s2_entryHigh, 1), ta.shift(s2_entryLow, 1)
    s2_chanH = eh1 - el1
    with np.errstate(invalid="ignore"):
        s2_breakHi = c > eh1
        s2_breakLo = c < el1
        s2_extUp = ~np.isnan(s2_sma) & (c > s2_sma + atr * 1.5)
        s2_extDn = ~np.isnan(s2_sma) & (c < s2_sma - atr * 1.5)
    s2_hasVol = s2_volSpike | volAboveAvg
    s2_trigL = s2_breakHi & ~s2_extUp & s2_hasVol
    s2_trigS = s2_breakLo & ~s2_extDn & s2_hasVol
    adxMom = np.select([adxVal > p.adxTrendThr, adxVal > p.adxRangeThr], [18.0, 10.0], 0.0)
    s2_htf = np.select([regimeBreakout, regime == 4, R0], [15.0, 10.0, 5.0], 0.0)
    s2_scoreLong, s2_parts = rubric_parts(s2_trigL,
        W(~np.isnan(s2_sma) & (c > s2_sma), 12.0) + W(aboveLT, 8.0) + W(ltUp, 5.0),
        adxMom + W(diPlus > diMinus, 7.0),
        W(atrExpanding, 8.0) + W(bbwExpanding, 7.0) + W(dfl > 70.0, 5.0),
        np.select([s2_volSpike, volAboveAvg], [15.0, 8.0], 0.0), s2_htf)
    s2_scoreShort = rubric(s2_trigS,
        W(~np.isnan(s2_sma) & (c < s2_sma), 12.0) + W(belowLT, 8.0) + W(ltDn, 5.0),
        adxMom + W(diMinus > diPlus, 7.0),
        W(atrExpanding, 8.0) + W(bbwExpanding, 7.0) + W(dfh > 70.0, 5.0),
        np.select([s2_volSpike, volAboveAvg], [15.0, 8.0], 0.0), s2_htf)

    # ── S3 ──
    s3_fast = ta.ema(c, p.s3_fastEMA)
    s3_slow = ta.ema(c, p.s3_slowEMA)
    s3_trend = ta.ema(c, p.s3_trendEMA)
    _, _, s3_hist = ta.macd(c, p.s3_macdFast, p.s3_macdSlow, p.s3_macdSig)
    s3_anchor = ta.vwma(c, v, 20)                      # daily chart → vwma proxy
    s3_bsUp = ta.barssince(ta.crossover(s3_fast, s3_slow))
    s3_bsDn = ta.barssince(ta.crossunder(s3_fast, s3_slow))
    with np.errstate(invalid="ignore"):
        s3_trigL = ~np.isnan(s3_bsUp) & (s3_bsUp <= p.s3_crossMax) & (rsi14 <= 70)
        s3_trigS = ~np.isnan(s3_bsDn) & (s3_bsDn <= p.s3_crossMax) & (rsi14 >= 30)
    dRoc20 = ta.nz(R["dRoc20"])
    h1 = ta.nz(ta.shift(s3_hist, 1))
    s3_htf = np.select([regimeMomentum, regime == 4, regime == 2, R0], [15.0, 10.0, 8.0, 5.0], 0.0)
    with np.errstate(invalid="ignore"):
        s3_scoreLong, s3_parts = rubric_parts(s3_trigL,
            W(c > s3_trend, 12.0) + W(c > s3_anchor, 8.0) + W(aboveLT, 5.0),
            np.select([(s3_hist > 0) & (rsi14 > 50), s3_hist > 0], [15.0, 8.0], 0.0) + W(dRoc20 > 3.0, 6.0) + W(s3_hist > h1, 4.0),
            W(s3_fast > s3_slow, 8.0) + W((c - s3_trend) < atr * 3.0, 6.0) + W(atrSane, 6.0),
            volScore, s3_htf)
        s3_scoreShort = rubric(s3_trigS,
            W(c < s3_trend, 12.0) + W(c < s3_anchor, 8.0) + W(belowLT, 5.0),
            np.select([(s3_hist < 0) & (rsi14 < 50), s3_hist < 0], [15.0, 8.0], 0.0) + W(dRoc20 < -3.0, 6.0) + W(s3_hist < h1, 4.0),
            W(s3_fast < s3_slow, 8.0) + W((s3_trend - c) < atr * 3.0, 6.0) + W(atrSane, 6.0),
            volScore, s3_htf)

    # ── S4 ──
    wkF, wkS, wkC, wkADX = R["s4_wkF"], R["s4_wkS"], R["s4_wkC"], R["s4_wkADX"]
    s4_dEMA = ta.ema(c, p.s4_dailyEMA)
    s4_macd, s4_sig, _ = ta.macd(c, 12, 26, 9)
    with np.errstate(invalid="ignore"):
        s4_wkBull = ~np.isnan(wkF) & ~np.isnan(wkS) & (wkF > wkS) & (wkC > wkF)
        s4_wkBear = ~np.isnan(wkF) & ~np.isnan(wkS) & (wkF < wkS) & (wkC < wkF)
        s4_pbBuy = (rsi14 < p.s4_rsiPBLo) & (rsi14 > 25)
        s4_pbSell = (rsi14 > p.s4_rsiPBHi) & (rsi14 < 75)
        c1, e1 = ta.shift(c, 1), ta.shift(s4_dEMA, 1)
        s4_bounce = (c > s4_dEMA) & (c1 <= e1)
        s4_reject = (c < s4_dEMA) & (c1 >= e1)
    s4_trigL = s4_wkBull & (s4_pbBuy | s4_bounce)
    s4_trigS = s4_wkBear & (s4_pbSell | s4_reject)
    dMom = ta.nz(R["dMom121"])
    s4_htf = np.select([regimeTrend, regime == 3, R0], [15.0, 10.0, 5.0], 0.0)
    with np.errstate(invalid="ignore"):
        s4_scoreLong, s4_parts = rubric_parts(s4_trigL,
            W(s4_wkBull, 15.0) + W(aboveLT, 10.0),
            W(ta.nz(wkADX) > 20.0, 10.0) + W(s4_macd > s4_sig, 8.0) + W(dMom > 0.0, 7.0),
            np.select([s4_pbBuy, s4_bounce], [12.0, 8.0], 0.0) + W(atrSane, 8.0),
            volScore, s4_htf)
        s4_scoreShort = rubric(s4_trigS,
            W(s4_wkBear, 15.0) + W(belowLT, 10.0),
            W(ta.nz(wkADX) > 20.0, 10.0) + W(s4_macd < s4_sig, 8.0) + W(dMom < 0.0, 7.0),
            np.select([s4_pbSell, s4_reject], [12.0, 8.0], 0.0) + W(atrSane, 8.0),
            volScore, s4_htf)

    # ── winner selection [F3] ──
    if p.useRegimeFilter:
        s1_al = (regime == 1) | R0
        s2_al = (regime == 2) | (regime == 4) | R0
        s3_al = (regime == 3) | (regime == 4) | R0
        s4_al = (regime == 4) | R0
    else:
        s1_al = s2_al = s3_al = s4_al = np.ones(n, bool)
    sh = p.shortEnabled
    s1L, s2L, s3L, s4L = W(s1_al, s1_scoreLong), W(s2_al, s2_scoreLong), W(s3_al, s3_scoreLong), W(s4_al, s4_scoreLong)
    s1S = W(s1_al, s1_scoreShort) if sh else np.zeros(n)
    s2S = W(s2_al, s2_scoreShort) if sh else np.zeros(n)
    s3S = W(s3_al, s3_scoreShort) if sh else np.zeros(n)
    s4S = W(s4_al, s4_scoreShort) if sh else np.zeros(n)
    bestLongScore = np.maximum.reduce([s1L, s2L, s3L, s4L])
    bestLongStrat = np.where(bestLongScore <= 0, 0, np.select([bestLongScore == s1L, bestLongScore == s2L, bestLongScore == s3L], [1, 2, 3], 4))
    bestShortScore = np.maximum.reduce([s1S, s2S, s3S, s4S])
    bestShortStrat = np.where(bestShortScore <= 0, 0, np.select([bestShortScore == s1S, bestShortScore == s2S, bestShortScore == s3S], [1, 2, 3], 4))
    isLong = bestLongScore >= bestShortScore
    bestScore = np.where(isLong, bestLongScore, bestShortScore)
    bestStrat = np.where(isLong, bestLongStrat, bestShortStrat)

    if p.version == "v3":
        # Per-strategy ELIGIBILITY replaces score-argmax. Each strategy has its own
        # validated gate; the winner is the highest-priority eligible one.
        elig = {
            1: s1_trigL & (s1_parts[:, 0] >= p.s1_trendGate) if p.s1_enabled else np.zeros(n, bool),
            2: s2_trigL & (s2_scoreLong >= profile.min_score) if p.s2_enabled else np.zeros(n, bool),
            3: s3_trigL & ((s3_scoreLong >= p.s3_gate) if p.s3_useThreshold else True),
            4: s4_trigL & (s4_scoreLong >= p.s4_minScore),
        }
        bestStrat = np.zeros(n, int)
        for k in reversed(p.priority):          # lowest priority first so higher overwrites
            bestStrat = np.where(elig[k], k, bestStrat)
        isLong = np.ones(n, bool)
        scores_by = {1: s1_scoreLong, 2: s2_scoreLong, 3: s3_scoreLong, 4: s4_scoreLong}
        bestScore = np.select([bestStrat == k for k in (1, 2, 3, 4)], [scores_by[k] for k in (1, 2, 3, 4)], 0.0)

    # ── risk levels [F7][F8] ──
    stopScale = profile.atr_stop_mult / 1.5
    tpScale = stopScale
    s1_stopD = atr * 1.20 * stopScale
    s2_stopD_long = np.maximum(atr * 0.80 * stopScale, np.abs(c - eh1) + atr * 0.30)
    s2_stopD_short = np.maximum(atr * 0.80 * stopScale, np.abs(el1 - c) + atr * 0.30)
    s2_stopD = np.where(isLong, s2_stopD_long, s2_stopD_short)
    s3_stopD = atr * 1.80 * stopScale
    s4_stopD = atr * 2.50 * stopScale
    stopDist = np.select([bestStrat == 1, bestStrat == 2, bestStrat == 3], [s1_stopD, s2_stopD, s3_stopD], s4_stopD)
    s1_tpD = np.minimum(np.maximum(np.abs(ta.nz(bbMid, c) - c), atr * 1.5 * tpScale), atr * 4.0 * tpScale)
    s2_tpD = np.maximum(ta.nz(s2_chanH, atr * 2.0 * tpScale), atr * 1.5 * tpScale)
    s3_tpD = atr * 3.0 * tpScale
    s4_tpD = atr * 4.0 * tpScale
    tpDist = np.select([bestStrat == 1, bestStrat == 2, bestStrat == 3], [s1_tpD, s2_tpD, s3_tpD], s4_tpD)
    mt = p.mintick
    entryRef = ta.round_to_mintick(c, mt)
    stopPrice = ta.round_to_mintick(np.where(isLong, c - stopDist, c + stopDist), mt)
    tpPrice = ta.round_to_mintick(np.where(isLong, c + tpDist, c - tpDist), mt)
    realRisk = np.abs(entryRef - stopPrice)
    realRwd = np.abs(tpPrice - entryRef)
    with np.errstate(invalid="ignore", divide="ignore"):
        rrRatio = np.where(realRisk > 0, realRwd / realRisk, 0.0)
    rrOk = rrRatio >= profile.min_rr

    # ── gates [F6] ──
    warmupOk = ((np.arange(n) >= 100) & ~np.isnan(R["dAtr"]) & ~np.isnan(dSma200) & ~np.isnan(bbwSMA) &
                ~np.isnan(rvPctile) & ~np.isnan(dAtrPct) & (ta.nz(R["dCtxBars"]) >= ta.pine_round(252 * 0.8)))
    dAdv = R["dAdvUsd"]
    liquidityOk = ((p.minDollarVol <= 0) | (~np.isnan(dAdv) & (dAdv >= p.minDollarVol * 1e6))) & ((p.minPrice <= 0) | (c >= p.minPrice))
    if p.version == "v3":
        eligible = warmupOk & (bestStrat > 0) & rrOk & liquidityOk
    else:
        eligible = warmupOk & (bestStrat > 0) & (bestScore >= profile.min_score) & rrOk & liquidityOk

    # [F13] cooldown is sequential — the only state the engine carries.
    fired = np.zeros(n, bool)
    last = 0
    cd_ms = profile.cooldown_min * 60000
    for t in range(n):
        if eligible[t] and (last == 0 or time_ms[t] - last >= cd_ms):
            fired[t] = True
            last = time_ms[t]

    dist52Comp = np.where(bestStrat == 1, dfh, dfl)
    compositeScore = bestScore * 0.50 + regimeConf * 0.20 + ta.nz(rvPctile, 50.0) * 0.15 + (100.0 - ta.nz(dAtrPct, 50.0)) * 0.05 + dist52Comp * 0.10

    out = pd.DataFrame({
        "t": bars.t.values, "date": dates_et.date, "o": o, "h": h, "l": l, "c": c, "v": v,
        "atr": atr, "adx": adxVal, "rsi14": rsi14, "chop": chop, "bbw": bbw, "rvPctile": rvPctile,
        "trendScore": trendScore, "breakoutScore": breakoutScore, "meanRevScore": meanRevScore, "momentumScore": momentumScore,
        "regime": regime, "regimeConf": regimeConf,
        "s1L": s1L, "s2L": s2L, "s3L": s3L, "s4L": s4L, "s1S": s1S, "s2S": s2S, "s3S": s3S, "s4S": s4S,
        "s1_trigL": s1_trigL, "s2_trigL": s2_trigL, "s3_trigL": s3_trigL, "s4_trigL": s4_trigL,
        "s1_raw": s1_scoreLong, "s2_raw": s2_scoreLong, "s3_raw": s3_scoreLong, "s4_raw": s4_scoreLong,
        "s1_al": s1_al, "s2_al": s2_al, "s3_al": s3_al, "s4_al": s4_al,
        "bestScore": bestScore, "bestStrat": bestStrat, "isLong": isLong,
        "entryRef": entryRef, "stopPrice": stopPrice, "tpPrice": tpPrice, "realRisk": realRisk, "rrRatio": rrRatio,
        "warmupOk": warmupOk, "liquidityOk": liquidityOk, "rrOk": rrOk, "eligible": eligible, "fired": fired,
        "compositeScore": compositeScore,
        "distFromHi": distFromHi, "distFromLo": distFromLo, "dAdvUsd": dAdv, "dAtrPct": dAtrPct, "dMom121": R["dMom121"],
        # per-strategy geometry (long side), for labelling every trigger event, not only the winner
        "s1_stopD": s1_stopD, "s2_stopD": s2_stopD_long, "s3_stopD": s3_stopD, "s4_stopD": s4_stopD,
        "s1_tpD": s1_tpD, "s2_tpD": s2_tpD, "s3_tpD": s3_tpD, "s4_tpD": s4_tpD,
        "s1_trigS": s1_trigS, "s2_trigS": s2_trigS, "s3_trigS": s3_trigS, "s4_trigS": s4_trigS,
        "s1_rawS": s1_scoreShort, "s2_rawS": s2_scoreShort, "s3_rawS": s3_scoreShort, "s4_rawS": s4_scoreShort,
        "s2_stopD_short": s2_stopD_short,
        "dRoc20": R["dRoc20"], "dRoc60": R["dRoc60"], "dSma200": dSma200,
    })
    for k, parts in (("s1", s1_parts), ("s2", s2_parts), ("s3", s3_parts), ("s4", s4_parts)):
        for j, name in enumerate(("trend", "mom", "loc", "vol", "htf")):
            out[f"{k}_{name}"] = parts[:, j]
    out.attrs["profile"] = profile.name
    return out


REGIME_NAMES = {0: "NEUTRAL", 1: "MEAN_REV", 2: "BREAKOUT", 3: "MOMENTUM", 4: "TRENDING"}
STRAT_NAMES = {1: "S1_MeanRev", 2: "S2_Breakout", 3: "S3_Momentum", 4: "S4_MTF"}
