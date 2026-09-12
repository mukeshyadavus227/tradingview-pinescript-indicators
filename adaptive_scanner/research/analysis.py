#!/usr/bin/env python3
"""
Phase 2 validation on the event tables produced by build_events.py.

Everything here answers one of four questions, in order of importance:
  1. Does the SCORE predict outcome within a strategy?   (decile curve, Spearman, walk-forward OOS)
  2. Does each strategy carry edge at all, in which regime? (expectancy matrix, ablation baseline)
  3. Which rubric components carry the signal?             (component ablation)
  4. Would the deployed set survive multiple-testing and costs? (DSR, PBO/CSCV, cost curve)

R is measured in units of initial risk (entry-to-stop). R_net3 (3 bps round
trip) is the headline number; the full cost curve is reported alongside.
"""
import sys, json, itertools
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RCOL = "R_net3"
STRATS = ["S1_MeanRev", "S2_Breakout", "S3_Momentum", "S4_MTF"]
REGIMES = ["NEUTRAL", "MEAN_REV", "BREAKOUT", "MOMENTUM", "TRENDING"]
COMPONENTS = ["trend", "mom", "loc", "vol", "htf"]
rng = np.random.default_rng(7)


# ────────────────────────────────────────────────────────────────────────────
def summarise(df, col=RCOL):
    if len(df) == 0:
        return dict(n=0)
    r = df[col].values
    wins, losses = r[r > 0], r[r <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf
    ci = stats.t.interval(0.95, len(r) - 1, loc=r.mean(), scale=stats.sem(r)) if len(r) > 2 else (np.nan, np.nan)
    return dict(n=len(r), hit=float((r > 0).mean()), meanR=float(r.mean()), medR=float(np.median(r)),
                ci_lo=float(ci[0]), ci_hi=float(ci[1]), pf=float(pf), sharpe=float(r.mean() / r.std(ddof=1)) if r.std(ddof=1) > 0 else np.nan,
                tp=float((df.reason.str.startswith("TP")).mean()), sl=float((df.reason.str.startswith("SL")).mean()),
                time=float((df.reason == "TIME").mean()), bars=float(df.bars_held.mean()))


def fmt_row(d):
    if d.get("n", 0) == 0:
        return "| 0 | | | | | | | |"
    return (f"| {d['n']:,} | {d['hit']:.1%} | {d['meanR']:+.3f} | [{d['ci_lo']:+.2f}, {d['ci_hi']:+.2f}] | {d['medR']:+.2f} "
            f"| {d['pf']:.2f} | {d['tp']:.0%}/{d['sl']:.0%}/{d['time']:.0%} | {d['bars']:.1f} |")


HDR = "| n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |\n|---:|---:|---:|:---:|---:|---:|:---:|---:|"


# ────────────────────────────────────────────────────────────────────────────
def decile_curve(ev, strat, col=RCOL, q=10):
    d = ev[(ev.strat == strat) & ev.is_long & (ev.score > 0)]
    if len(d) < 50:
        return None, d
    # Deciles by score rank within strategy; ties broken by order to keep bins full.
    d = d.copy()
    d["dec"] = pd.qcut(d.score.rank(method="first"), q, labels=False) + 1
    g = d.groupby("dec").agg(n=(col, "size"), score_lo=("score", "min"), score_hi=("score", "max"),
                             meanR=(col, "mean"), hit=(col, lambda x: (x > 0).mean()))
    rho, p = stats.spearmanr(d.score, d[col])
    # Monotonicity: Spearman of decile index vs decile mean
    mono, _ = stats.spearmanr(g.index, g.meanR)
    return dict(table=g, rho=rho, p=p, mono=mono, n=len(d)), d


def walk_forward(ev, strat, col=RCOL, train_years=3, q=5):
    """Rolling by calendar year: fit decile→meanR on train, score OOS test year.
    Reports OOS Spearman(predicted, realised) per fold and top-vs-bottom quintile OOS expectancy."""
    d = ev[(ev.strat == strat) & ev.is_long & (ev.score > 0)].copy()
    if len(d) < 200:
        return None
    d["year"] = pd.to_datetime(d.date).dt.year
    years = sorted(d.year.unique())
    folds = []
    for i in range(train_years, len(years)):
        tr = d[d.year.isin(years[i - train_years:i])]
        te = d[d.year == years[i]]
        if len(tr) < 100 or len(te) < 30:
            continue
        cuts = np.unique(np.quantile(tr.score, np.linspace(0, 1, q + 1)))
        if len(cuts) < 3:
            continue
        tr_bin = pd.cut(tr.score, cuts, include_lowest=True, labels=False)
        pred_map = tr.groupby(tr_bin)[col].mean()
        te_bin = pd.cut(te.score, cuts, include_lowest=True, labels=False)
        pred = te_bin.map(pred_map)
        ok = pred.notna()
        if ok.sum() < 30:
            continue
        rho, p = stats.spearmanr(pred[ok], te[col][ok])
        top = te[col][ok & (te_bin == te_bin[ok].max())]
        bot = te[col][ok & (te_bin == te_bin[ok].min())]
        folds.append(dict(test_year=int(years[i]), n_train=len(tr), n_test=int(ok.sum()), oos_rho=float(rho), p=float(p),
                          top_meanR=float(top.mean()) if len(top) else np.nan, bot_meanR=float(bot.mean()) if len(bot) else np.nan,
                          all_meanR=float(te[col][ok].mean())))
    if not folds:
        return None
    f = pd.DataFrame(folds)
    pooled_rho = float(f.oos_rho.mean())
    frac_pos = float((f.oos_rho > 0).mean())
    return dict(folds=f, pooled_rho=pooled_rho, frac_pos=frac_pos, top_minus_bot=float((f.top_meanR - f.bot_meanR).mean()))


def component_ablation(ev, strat, col=RCOL, top_frac=0.25):
    d = ev[(ev.strat == strat) & ev.is_long & (ev.score > 0)].copy()
    if len(d) < 100:
        return None
    rows = []
    full_top = d[d.score >= d.score.quantile(1 - top_frac)]
    base = float(full_top[col].mean())
    rows.append(dict(component="(full score)", rho=stats.spearmanr(d.score, d[col])[0], top_meanR=base, delta=0.0, n_top=len(full_top)))
    for cpt in COMPONENTS:
        cc = f"c_{cpt}"
        rho_c = stats.spearmanr(d[cc], d[col])[0] if d[cc].std() > 0 else np.nan
        s_wo = d.score - d[cc]
        top = d[s_wo >= s_wo.quantile(1 - top_frac)]
        rows.append(dict(component=f"− {cpt}", rho=rho_c, top_meanR=float(top[col].mean()), delta=float(top[col].mean() - base), n_top=len(top)))
    return pd.DataFrame(rows)


# ────────────────────────────────────────────────────────────────────────────
def deflated_sharpe(r, n_trials, sr_var):
    """Bailey & López de Prado (2014). r: per-trade R sequence. Returns (SR, SR0, DSR, MinTRL95)."""
    T = len(r)
    if T < 10 or r.std(ddof=1) == 0:
        return np.nan, np.nan, np.nan, np.nan
    sr = r.mean() / r.std(ddof=1)
    g3, g4 = stats.skew(r), stats.kurtosis(r, fisher=False)
    em = 0.5772156649
    sr0 = np.sqrt(sr_var) * ((1 - em) * stats.norm.ppf(1 - 1 / n_trials) + em * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
    denom = np.sqrt(max(1e-9, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    dsr = stats.norm.cdf((sr - sr0) * np.sqrt(T - 1) / denom)
    mintrl = 1 + (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) * (stats.norm.ppf(0.95) / sr) ** 2 if sr > 0 else np.inf
    return float(sr), float(sr0), float(dsr), float(mintrl)


def config_monthly_matrix(ev, col=RCOL):
    """Rows = months, columns = configurations (strategy × min score × aligned-only). Value = sum of R that month."""
    d = ev[ev.is_long & (ev.score > 0)].copy()
    d["month"] = pd.to_datetime(d.date).dt.to_period("M")
    months = pd.period_range(d.month.min(), d.month.max(), freq="M")
    cols = {}
    for strat in STRATS:
        for thr in (0, 50, 60, 70, 75, 80, 85):
            for al in (False, True):
                m = (d.strat == strat) & (d.score >= thr) & ((d.aligned) if al else True)
                s = d[m].groupby("month")[col].sum().reindex(months, fill_value=0.0)
                cols[f"{strat}|>={thr}|{'aligned' if al else 'any'}"] = s.values
    return pd.DataFrame(cols, index=months)


def pbo_cscv(M, S=16, n_combos=800):
    """Probability of Backtest Overfitting via CSCV (Bailey et al. 2017). M: T×N matrix of period returns."""
    T, N = M.shape
    blocks = np.array_split(np.arange(T), S)
    half = S // 2
    combos = list(itertools.combinations(range(S), half))
    if len(combos) > n_combos:
        combos = [combos[i] for i in rng.choice(len(combos), n_combos, replace=False)]
    logits = []
    for tr_blocks in combos:
        te_blocks = [b for b in range(S) if b not in tr_blocks]
        tr = np.concatenate([blocks[b] for b in tr_blocks]); te = np.concatenate([blocks[b] for b in te_blocks])
        def sharpe(X):
            mu, sd = X.mean(axis=0), X.std(axis=0, ddof=1)
            return np.where(sd > 0, mu / np.where(sd > 0, sd, 1), -np.inf)
        best = int(np.argmax(sharpe(M[tr])))
        te_sr = sharpe(M[te])
        rank = (te_sr < te_sr[best]).sum() + 0.5 * (te_sr == te_sr[best]).sum()
        w = rank / N
        w = min(max(w, 1e-6), 1 - 1e-6)
        logits.append(np.log(w / (1 - w)))
    logits = np.array(logits)
    return float((logits < 0).mean()), float(logits.mean())


# ────────────────────────────────────────────────────────────────────────────
def run(profile):
    ev = pd.read_csv(OUT / f"events_{profile}.csv")
    ev["date"] = pd.to_datetime(ev.date)
    fired = ev[ev.fired]
    base = ev[ev.is_long & (ev.score > 0)]
    years = (ev.date.max() - ev.date.min()).days / 365.25
    n_sym = ev.symbol.nunique()
    L = []
    P = L.append
    P(f"# Phase 2 validation — profile {profile}\n")
    P(f"Universe: {n_sym} symbols, {ev.date.min().date()} → {ev.date.max().date()} ({years:.1f} years). "
      f"Trigger events: {len(ev):,} ({int(ev.is_long.sum()):,} long). Deployed (fired): {len(fired):,} "
      f"= {len(fired)/n_sym/years:.2f} per symbol-year.\n")
    P(f"R is in units of initial risk; headline column is `{RCOL}` (3 bps round-trip). "
      "**Survivorship caveat:** the universe is today's liquid names, so long-side baselines are optimistic.\n")

    # 1. Deployed set
    P("## 1. Deployed set (what the scanner would actually have fired)\n")
    P("| strategy " + HDR[1:])
    for s in STRATS:
        P(f"| {s} " + fmt_row(summarise(fired[fired.strat == s])))
    P(f"| **ALL** " + fmt_row(summarise(fired)))
    P("")
    P("Exit-reason split is TP / SL / TIME. A TIME share near 50% means the horizon, not the thesis, is deciding most trades.\n")

    # 2. Ablation baseline
    P("## 2. Ablation baseline — every long trigger event, no score filter\n")
    P("If the deployed row is not clearly better than this, the score is not adding anything the trigger did not already have.\n")
    P("| strategy | population " + HDR[1:])
    for s in STRATS:
        P(f"| {s} | all triggers " + fmt_row(summarise(base[base.strat == s])))
        P(f"| {s} | aligned only " + fmt_row(summarise(base[(base.strat == s) & base.aligned])))
        P(f"| {s} | aligned, score ≥ min " + fmt_row(summarise(base[(base.strat == s) & base.aligned & (base.score >= (75 if profile == 'SWING' else 70))])))
    P("")

    # 3. Decile curves
    P("## 3. Does the score predict outcome? Expectancy by score decile (long trigger events, within strategy)\n")
    dec_summary = {}
    for s in STRATS:
        res, _ = decile_curve(ev, s)
        if res is None:
            P(f"**{s}:** too few events for deciles.\n"); continue
        g = res["table"]
        dec_summary[s] = dict(rho=res["rho"], p=res["p"], mono=res["mono"], n=res["n"])
        P(f"**{s}** — n={res['n']:,}, Spearman(score, R) = {res['rho']:+.3f} (p={res['p']:.2g}), decile monotonicity = {res['mono']:+.2f}\n")
        P("| decile | score range | n | hit | mean R |\n|---:|:---:|---:|---:|---:|")
        for dcl, row in g.iterrows():
            P(f"| {dcl} | {row.score_lo:.0f}–{row.score_hi:.0f} | {int(row.n):,} | {row.hit:.1%} | {row.meanR:+.3f} |")
        P("")

    # 4. Walk-forward
    P("## 4. Walk-forward: does the score→expectancy map hold out of sample?\n")
    P("Rolling 3-year train / 1-year test. Fit a quintile→mean-R map on train, apply to test, report Spearman(predicted, realised).\n")
    P("| strategy | folds | mean OOS ρ | folds with ρ>0 | mean(top − bottom quintile R) |\n|---|---:|---:|---:|---:|")
    wf_summary = {}
    for s in STRATS:
        w = walk_forward(ev, s)
        if w is None:
            P(f"| {s} | — | | | |"); continue
        wf_summary[s] = w
        P(f"| {s} | {len(w['folds'])} | {w['pooled_rho']:+.3f} | {w['frac_pos']:.0%} | {w['top_minus_bot']:+.3f} |")
    P("")
    for s, w in wf_summary.items():
        P(f"<details><summary>{s} folds</summary>\n")
        P("| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |\n|---:|---:|---:|---:|---:|---:|---:|---:|")
        for _, f in w["folds"].iterrows():
            P(f"| {f.test_year} | {f.n_train:,} | {f.n_test:,} | {f.oos_rho:+.2f} | {f.p:.2f} | {f.top_meanR:+.2f} | {f.bot_meanR:+.2f} | {f.all_meanR:+.2f} |")
        P("\n</details>\n")

    # 5. Regime matrix
    P("## 5. Strategy × regime expectancy (long trigger events, aligned only)\n")
    P("| strategy | " + " | ".join(REGIMES) + " |\n|---|" + "---:|" * len(REGIMES))
    for s in STRATS:
        cells = []
        for rg in REGIMES:
            d = base[(base.strat == s) & base.aligned & (base.regime == rg)]
            cells.append(f"{d[RCOL].mean():+.2f} (n={len(d):,})" if len(d) >= 20 else f"— (n={len(d)})")
        P(f"| {s} | " + " | ".join(cells) + " |")
    P("")
    P("The alignment filter makes most cells structurally empty: S1 only trades in MEAN_REV/NEUTRAL, S4 only in TRENDING/NEUTRAL.\n")

    # 6. Component ablation
    P("## 6. Component ablation — which rubric parts carry the signal?\n")
    P("ρ = Spearman of the component alone vs R. Top-quartile expectancy re-selected by the score WITHOUT that component; Δ vs the full score. A negative Δ means the component was helping.\n")
    for s in STRATS:
        a = component_ablation(ev, s)
        if a is None:
            continue
        P(f"**{s}**\n\n| component | ρ vs R | top-25% mean R | Δ | n |\n|---|---:|---:|---:|---:|")
        for _, r in a.iterrows():
            P(f"| {r.component} | {r.rho:+.3f} | {r.top_meanR:+.3f} | {r.delta:+.3f} | {int(r.n_top):,} |")
        P("")

    # 7. Cost curve
    P("## 7. Cost sensitivity (deployed set)\n")
    P("| round-trip bps | " + " | ".join(STRATS) + " | ALL |\n|---:|" + "---:|" * (len(STRATS) + 1))
    for bps in (0, 1, 3, 5, 10):
        col = f"R_net{bps}"
        cells = [f"{fired[fired.strat == s][col].mean():+.3f}" if (fired.strat == s).sum() > 0 else "—" for s in STRATS]
        P(f"| {bps} | " + " | ".join(cells) + f" | {fired[col].mean():+.3f} |")
    P("")

    # 8. DSR + PBO
    P("## 8. Multiple-testing corrections\n")
    M = config_monthly_matrix(ev)
    sr_per_config = (M.mean() / M.std(ddof=1)).replace([np.inf, -np.inf], np.nan).dropna()
    n_cfg = M.shape[1]
    # Deflate the deployed set's MONTHLY Sharpe against the MONTHLY Sharpe
    # dispersion of the configuration family — same units on both sides.
    fm = fired.copy(); fm["month"] = fm.date.dt.to_period("M")
    dep_monthly = fm.groupby("month")[RCOL].sum().reindex(M.index, fill_value=0.0).values
    seq = fired.sort_values("date")[RCOL].values
    sr_trade = seq.mean() / seq.std(ddof=1)
    P(f"**Deployed set:** per-trade SR = {sr_trade:+.3f} over {len(seq):,} trades; monthly SR (sum of R per month) = "
      f"{dep_monthly.mean()/dep_monthly.std(ddof=1):+.3f} over {len(dep_monthly)} months.\n")
    P("**Deflated Sharpe** (Bailey & López de Prado), monthly units. N = number of configurations the selection is "
      "assumed to have searched. The 56 here are only the ones this harness enumerated; the hand-tuned weights, "
      "thresholds and ATR multiples were chosen over an unknown, larger N, so read the row for N=500 as the honest one.\n")
    P("| N trials | E[max SR | null] | DSR | MinTRL (months) |\n|---:|---:|---:|---:|")
    dsr_rows = {}
    for N in (56, 200, 500, 2000):
        sr, sr0, dsr, mintrl = deflated_sharpe(dep_monthly, n_trials=N, sr_var=float(sr_per_config.var()))
        dsr_rows[N] = dict(sr=sr, sr0=sr0, dsr=dsr, mintrl=mintrl)
        P(f"| {N} | {sr0:+.3f} | **{dsr:.3f}** | {mintrl:,.0f} |")
    sr, sr0, dsr, mintrl = (dsr_rows[500][k] for k in ("sr", "sr0", "dsr", "mintrl"))
    P("")
    pbo, mean_logit = pbo_cscv(M.values)
    P(f"**PBO via CSCV** over {n_cfg} (strategy × threshold × alignment) configurations on {M.shape[0]} monthly periods, "
      f"S=16 blocks: **PBO = {pbo:.2f}** (mean logit {mean_logit:+.2f}). Reject the configuration family if PBO > 0.5.\n")
    P("Best in-sample configurations by monthly Sharpe:\n")
    P("| configuration | monthly SR | months active |\n|---|---:|---:|")
    for cfg, v in sr_per_config.sort_values(ascending=False).head(8).items():
        P(f"| {cfg} | {v:+.3f} | {int((M[cfg] != 0).sum())} |")
    P("")

    # 9. Shorts (informational)
    P("## 9. Short-side trigger events (not deployed; informational)\n")
    P("| strategy " + HDR[1:])
    sh = ev[~ev.is_long & (ev.score > 0)]
    for s in STRATS:
        P(f"| {s} " + fmt_row(summarise(sh[sh.strat == s])))
    P("")

    # 10. Time-stop diagnostic
    P("## 10. Time-stop diagnostic (deployed set)\n")
    t = fired[fired.reason == "TIME"]
    if len(t):
        P(f"TIME exits: n={len(t):,}, mean R = {t[RCOL].mean():+.3f}, mean MFE = {t.mfe_R.mean():+.2f} R, "
          f"share that reached ≥ +1 R at some point = {(t.mfe_R >= 1).mean():.0%}, mean MAE = {t.mae_R.mean():+.2f} R.\n")
        P("A large MFE with a small final R says the target is too far for the horizon; a small MFE says the setup simply did not move.\n")

    (OUT / f"report_{profile}.md").write_text("\n".join(L))
    json.dump(dict(deciles=dec_summary, wf={k: dict(pooled_rho=v["pooled_rho"], frac_pos=v["frac_pos"], top_minus_bot=v["top_minus_bot"]) for k, v in wf_summary.items()},
                   dsr=dsr_rows, sr_trade=float(sr_trade), pbo=pbo,
                   deployed={s: summarise(fired[fired.strat == s]) for s in STRATS}, deployed_all=summarise(fired)),
              open(OUT / f"summary_{profile}.json", "w"), indent=1, default=float)
    print("\n".join(L))


if __name__ == "__main__":
    for prof in (sys.argv[1:] or ["SWING", "POSITIONAL"]):
        run(prof)
        print("\n" + "=" * 100 + "\n")
