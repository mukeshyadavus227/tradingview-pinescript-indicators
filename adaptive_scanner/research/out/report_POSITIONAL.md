# Phase 2 validation — profile POSITIONAL

Universe: 48 symbols, 2015-07-28 → 2026-09-10 (11.1 years). Trigger events: 59,951 (28,775 long). Deployed (fired): 1,806 = 3.38 per symbol-year.

R is in units of initial risk; headline column is `R_net3` (3 bps round-trip). **Survivorship caveat:** the universe is today's liquid names, so long-side baselines are optimistic.

## 1. Deployed set (what the scanner would actually have fired)

| strategy  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | 3 | 0.0% | -1.405 | [-2.37, -0.44] | -1.41 | 0.00 | 0%/100%/0% | 11.7 |
| S2_Breakout | 40 | 32.5% | +0.067 | [-0.48, +0.61] | -1.01 | 1.10 | 22%/65%/12% | 16.6 |
| S3_Momentum | 1,066 | 53.9% | +0.239 | [+0.17, +0.31] | +0.23 | 1.57 | 28%/38%/33% | 27.2 |
| S4_MTF | 697 | 61.5% | +0.340 | [+0.27, +0.41] | +0.33 | 2.23 | 22%/21%/56% | 33.2 |
| **ALL** | 1,806 | 56.3% | +0.272 | [+0.22, +0.32] | +0.26 | 1.73 | 26%/32%/41% | 29.3 |

Exit-reason split is TP / SL / TIME. A TIME share near 50% means the horizon, not the thesis, is deciding most trades.

## 2. Ablation baseline — every long trigger event, no score filter

If the deployed row is not clearly better than this, the score is not adding anything the trigger did not already have.

| strategy | population  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | all triggers | 3,516 | 52.5% | +0.266 | [+0.22, +0.31] | +0.48 | 1.54 | 44%/45%/11% | 16.7 |
| S1_MeanRev | aligned only | 350 | 47.7% | +0.102 | [-0.03, +0.23] | -1.00 | 1.19 | 44%/51%/4% | 14.1 |
| S1_MeanRev | aligned, score ≥ min | 28 | 39.3% | -0.121 | [-0.61, +0.36] | -1.01 | 0.82 | 36%/61%/4% | 14.4 |
| S2_Breakout | all triggers | 491 | 36.0% | +0.134 | [-0.02, +0.28] | -1.01 | 1.20 | 32%/63%/5% | 12.7 |
| S2_Breakout | aligned only | 296 | 33.4% | +0.065 | [-0.12, +0.25] | -1.01 | 1.09 | 28%/66%/6% | 13.7 |
| S2_Breakout | aligned, score ≥ min | 59 | 27.1% | -0.111 | [-0.54, +0.32] | -1.01 | 0.85 | 20%/69%/10% | 16.0 |
| S3_Momentum | all triggers | 16,762 | 53.9% | +0.231 | [+0.21, +0.25] | +0.19 | 1.57 | 27%/36%/36% | 27.6 |
| S3_Momentum | aligned only | 7,361 | 55.1% | +0.263 | [+0.24, +0.29] | +0.26 | 1.67 | 28%/35%/36% | 27.9 |
| S3_Momentum | aligned, score ≥ min | 2,466 | 51.5% | +0.199 | [+0.15, +0.25] | +0.07 | 1.47 | 27%/37%/34% | 27.5 |
| S4_MTF | all triggers | 8,006 | 57.3% | +0.211 | [+0.19, +0.23] | +0.20 | 1.67 | 17%/25%/56% | 33.2 |
| S4_MTF | aligned only | 2,954 | 58.0% | +0.246 | [+0.21, +0.28] | +0.23 | 1.80 | 19%/24%/55% | 33.0 |
| S4_MTF | aligned, score ≥ min | 1,042 | 62.0% | +0.333 | [+0.27, +0.39] | +0.35 | 2.24 | 21%/20%/57% | 33.4 |

## 3. Does the score predict outcome? Expectancy by score decile (long trigger events, within strategy)

**S1_MeanRev** — n=3,516, Spearman(score, R) = -0.006 (p=0.73), decile monotonicity = -0.38

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 21–26 | 352 | 56.0% | +0.295 |
| 2 | 26–34 | 352 | 56.2% | +0.330 |
| 3 | 34–36 | 351 | 56.7% | +0.290 |
| 4 | 36–41 | 352 | 60.5% | +0.506 |
| 5 | 41–42 | 351 | 46.7% | +0.111 |
| 6 | 42–47 | 352 | 52.0% | +0.257 |
| 7 | 47–49 | 351 | 50.1% | +0.229 |
| 8 | 49–54 | 352 | 47.2% | +0.114 |
| 9 | 54–59 | 351 | 52.7% | +0.346 |
| 10 | 59–82 | 352 | 46.6% | +0.182 |

**S2_Breakout** — n=491, Spearman(score, R) = -0.036 (p=0.42), decile monotonicity = -0.26

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 20–34 | 50 | 34.0% | -0.007 |
| 2 | 34–38 | 49 | 38.8% | +0.224 |
| 3 | 39–42 | 49 | 38.8% | +0.183 |
| 4 | 42–45 | 49 | 49.0% | +0.593 |
| 5 | 45–50 | 49 | 30.6% | -0.048 |
| 6 | 50–52 | 49 | 40.8% | +0.326 |
| 7 | 52–57 | 49 | 32.7% | +0.019 |
| 8 | 57–62 | 49 | 32.7% | +0.032 |
| 9 | 62–74 | 49 | 30.6% | -0.050 |
| 10 | 74–100 | 49 | 32.7% | +0.072 |

**S3_Momentum** — n=16,762, Spearman(score, R) = +0.001 (p=0.93), decile monotonicity = -0.10

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 6–35 | 1,677 | 52.0% | +0.197 |
| 2 | 35–48 | 1,676 | 53.8% | +0.230 |
| 3 | 48–56 | 1,676 | 55.1% | +0.217 |
| 4 | 56–60 | 1,676 | 55.7% | +0.282 |
| 5 | 60–64 | 1,676 | 56.2% | +0.287 |
| 6 | 64–66 | 1,676 | 54.3% | +0.215 |
| 7 | 66–69 | 1,676 | 55.0% | +0.267 |
| 8 | 69–74 | 1,676 | 53.5% | +0.207 |
| 9 | 74–79 | 1,676 | 54.4% | +0.276 |
| 10 | 79–100 | 1,677 | 49.5% | +0.133 |

**S4_MTF** — n=8,006, Spearman(score, R) = +0.063 (p=1.5e-08), decile monotonicity = +0.76

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 27–48 | 801 | 51.2% | +0.064 |
| 2 | 49–53 | 801 | 54.8% | +0.175 |
| 3 | 53–57 | 800 | 54.0% | +0.145 |
| 4 | 57–59 | 801 | 56.7% | +0.182 |
| 5 | 59–63 | 800 | 59.0% | +0.262 |
| 6 | 63–67 | 801 | 60.2% | +0.281 |
| 7 | 67–69 | 800 | 59.2% | +0.223 |
| 8 | 69–73 | 801 | 58.8% | +0.223 |
| 9 | 73–78 | 800 | 59.6% | +0.295 |
| 10 | 78–92 | 801 | 59.9% | +0.255 |

## 4. Walk-forward: does the score→expectancy map hold out of sample?

Rolling 3-year train / 1-year test. Fit a quintile→mean-R map on train, apply to test, report Spearman(predicted, realised).

| strategy | folds | mean OOS ρ | folds with ρ>0 | mean(top − bottom quintile R) |
|---|---:|---:|---:|---:|
| S1_MeanRev | 9 | +0.002 | 33% | -0.136 |
| S2_Breakout | 7 | -0.079 | 29% | -0.085 |
| S3_Momentum | 9 | -0.038 | 11% | -0.050 |
| S4_MTF | 9 | +0.025 | 56% | +0.136 |

<details><summary>S1_MeanRev folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 657.0 | 487.0 | -0.03 | 0.52 | -0.13 | +0.35 | +0.16 |
| 2019.0 | 966.0 | 217.0 | +0.15 | 0.03 | +0.17 | +1.09 | +0.82 |
| 2020.0 | 819.0 | 355.0 | +0.24 | 0.00 | -0.54 | +0.20 | -0.19 |
| 2021.0 | 1,060.0 | 194.0 | -0.09 | 0.21 | +0.52 | +0.37 | +0.53 |
| 2022.0 | 767.0 | 514.0 | -0.10 | 0.03 | +0.33 | +0.12 | +0.25 |
| 2023.0 | 1,063.0 | 313.0 | -0.02 | 0.78 | +0.28 | +0.40 | +0.31 |
| 2024.0 | 1,022.0 | 285.0 | -0.04 | 0.54 | +0.74 | +0.40 | +0.41 |
| 2025.0 | 1,113.0 | 310.0 | -0.12 | 0.04 | +0.25 | +0.06 | +0.41 |
| 2026.0 | 909.0 | 182.0 | +0.02 | 0.82 | +0.49 | +0.35 | +0.34 |

</details>

<details><summary>S2_Breakout folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019.0 | 114.0 | 63.0 | -0.03 | 0.81 | -0.28 | +0.52 | +0.09 |
| 2020.0 | 140.0 | 36.0 | -0.29 | 0.08 | +0.05 | -0.22 | -0.08 |
| 2021.0 | 141.0 | 48.0 | +0.16 | 0.29 | -1.01 | +0.26 | -0.17 |
| 2022.0 | 148.0 | 59.0 | -0.14 | 0.27 | +0.65 | +0.18 | +0.16 |
| 2023.0 | 143.0 | 55.0 | +0.07 | 0.62 | +0.79 | +0.27 | +0.31 |
| 2024.0 | 162.0 | 33.0 | -0.09 | 0.60 | +0.95 | +0.20 | +0.56 |
| 2025.0 | 147.0 | 30.0 | -0.22 | 0.25 | -0.09 | +0.43 | +0.23 |

</details>

<details><summary>S3_Momentum folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 3,533.0 | 1,566.0 | -0.07 | 0.00 | -0.16 | -0.08 | -0.11 |
| 2019.0 | 4,414.0 | 1,590.0 | -0.02 | 0.46 | +0.23 | +0.47 | +0.42 |
| 2020.0 | 4,532.0 | 1,430.0 | -0.03 | 0.22 | +0.43 | +0.26 | +0.33 |
| 2021.0 | 4,586.0 | 1,617.0 | -0.05 | 0.06 | +0.28 | +0.33 | +0.31 |
| 2022.0 | 4,637.0 | 1,474.0 | -0.03 | 0.27 | -0.18 | -0.03 | -0.19 |
| 2023.0 | 4,521.0 | 1,524.0 | -0.02 | 0.46 | +0.21 | +0.27 | +0.27 |
| 2024.0 | 4,615.0 | 1,371.0 | -0.03 | 0.24 | +0.13 | +0.44 | +0.33 |
| 2025.0 | 4,369.0 | 1,617.0 | +0.02 | 0.51 | +0.06 | +0.04 | +0.16 |
| 2026.0 | 4,512.0 | 1,040.0 | -0.11 | 0.00 | +0.27 | +0.01 | +0.11 |

</details>

<details><summary>S4_MTF folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 1,754.0 | 789.0 | -0.01 | 0.71 | -0.05 | -0.08 | -0.06 |
| 2019.0 | 2,366.0 | 608.0 | -0.00 | 0.97 | +0.35 | +0.45 | +0.45 |
| 2020.0 | 2,296.0 | 774.0 | +0.04 | 0.24 | +0.08 | -0.12 | +0.05 |
| 2021.0 | 2,171.0 | 968.0 | -0.05 | 0.12 | +0.60 | +0.32 | +0.42 |
| 2022.0 | 2,350.0 | 420.0 | -0.03 | 0.50 | -0.08 | -0.08 | -0.17 |
| 2023.0 | 2,162.0 | 582.0 | +0.13 | 0.00 | +0.28 | -0.06 | +0.13 |
| 2024.0 | 1,970.0 | 915.0 | +0.01 | 0.80 | +0.32 | +0.27 | +0.27 |
| 2025.0 | 1,917.0 | 601.0 | +0.12 | 0.00 | +0.34 | -0.02 | +0.20 |
| 2026.0 | 2,099.0 | 594.0 | +0.02 | 0.68 | +0.07 | +0.00 | +0.08 |

</details>

## 5. Strategy × regime expectancy (long trigger events, aligned only)

| strategy | NEUTRAL | MEAN_REV | BREAKOUT | MOMENTUM | TRENDING |
|---|---:|---:|---:|---:|---:|
| S1_MeanRev | +0.11 (n=335) | — (n=15) | — (n=0) | — (n=0) | — (n=0) |
| S2_Breakout | -0.02 (n=213) | — (n=0) | +0.33 (n=71) | — (n=0) | — (n=12) |
| S3_Momentum | +0.28 (n=6,139) | — (n=0) | — (n=0) | +0.19 (n=1,166) | +0.10 (n=56) |
| S4_MTF | +0.23 (n=2,825) | — (n=0) | — (n=0) | — (n=0) | +0.49 (n=129) |

The alignment filter makes most cells structurally empty: S1 only trades in MEAN_REV/NEUTRAL, S4 only in TRENDING/NEUTRAL.

## 6. Component ablation — which rubric parts carry the signal?

ρ = Spearman of the component alone vs R. Top-quartile expectancy re-selected by the score WITHOUT that component; Δ vs the full score. A negative Δ means the component was helping.

**S1_MeanRev**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | -0.006 | +0.229 | +0.000 | 1,284 |
| − trend | +0.003 | +0.217 | -0.012 | 938 |
| − mom | +0.102 | +0.232 | +0.003 | 1,183 |
| − loc | +0.044 | +0.231 | +0.002 | 1,201 |
| − vol | -0.060 | +0.345 | +0.116 | 1,024 |
| − htf | -0.071 | +0.242 | +0.013 | 1,201 |

**S2_Breakout**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | -0.036 | -0.008 | +0.000 | 158 |
| − trend | -0.105 | +0.048 | +0.056 | 130 |
| − mom | -0.009 | +0.091 | +0.098 | 175 |
| − loc | +0.011 | +0.051 | +0.059 | 123 |
| − vol | +0.013 | -0.034 | -0.026 | 125 |
| − htf | +0.018 | -0.023 | -0.015 | 190 |

**S3_Momentum**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | +0.001 | +0.213 | +0.000 | 4,334 |
| − trend | -0.014 | +0.202 | -0.011 | 4,196 |
| − mom | +0.000 | +0.251 | +0.038 | 5,959 |
| − loc | +0.003 | +0.196 | -0.018 | 4,443 |
| − vol | -0.001 | +0.219 | +0.005 | 4,496 |
| − htf | +0.011 | +0.207 | -0.006 | 4,377 |

**S4_MTF**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | +0.063 | +0.275 | +0.000 | 2,077 |
| − trend | +0.080 | +0.267 | -0.007 | 2,058 |
| − mom | +0.068 | +0.268 | -0.007 | 2,238 |
| − loc | +0.055 | +0.237 | -0.038 | 2,396 |
| − vol | -0.017 | +0.273 | -0.002 | 2,170 |
| − htf | +0.010 | +0.255 | -0.020 | 2,298 |

## 7. Cost sensitivity (deployed set)

| round-trip bps | S1_MeanRev | S2_Breakout | S3_Momentum | S4_MTF | ALL |
|---:|---:|---:|---:|---:|---:|
| 0 | -1.396 | +0.075 | +0.244 | +0.344 | +0.276 |
| 1 | -1.399 | +0.072 | +0.242 | +0.343 | +0.274 |
| 3 | -1.405 | +0.067 | +0.239 | +0.340 | +0.272 |
| 5 | -1.411 | +0.061 | +0.236 | +0.338 | +0.269 |
| 10 | -1.426 | +0.048 | +0.228 | +0.331 | +0.261 |

## 8. Multiple-testing corrections

**Deployed set:** per-trade SR = +0.243 over 1,806 trades; monthly SR (sum of R per month) = +0.459 over 135 months.

**Deflated Sharpe** (Bailey & López de Prado), monthly units. N = number of configurations the selection is assumed to have searched. The 56 here are only the ones this harness enumerated; the hand-tuned weights, thresholds and ATR multiples were chosen over an unknown, larger N, so read the row for N=500 as the honest one.

| N trials | E[max SR | null] | DSR | MinTRL (months) |
|---:|---:|---:|---:|
| 56 | +0.394 | **0.785** | 13 |
| 200 | +0.470 | **0.447** | 13 |
| 500 | +0.519 | **0.234** | 13 |
| 2000 | +0.586 | **0.062** | 13 |

**PBO via CSCV** over 56 (strategy × threshold × alignment) configurations on 135 monthly periods, S=16 blocks: **PBO = 0.06** (mean logit +1.44). Reject the configuration family if PBO > 0.5.

Best in-sample configurations by monthly Sharpe:

| configuration | monthly SR | months active |
|---|---:|---:|
| S4_MTF|>=60|aligned | +0.462 | 131 |
| S4_MTF|>=50|aligned | +0.432 | 132 |
| S4_MTF|>=70|aligned | +0.419 | 121 |
| S4_MTF|>=0|aligned | +0.412 | 132 |
| S4_MTF|>=60|any | +0.406 | 134 |
| S3_Momentum|>=0|any | +0.400 | 135 |
| S4_MTF|>=50|any | +0.395 | 134 |
| S3_Momentum|>=0|aligned | +0.393 | 134 |

## 9. Short-side trigger events (not deployed; informational)

| strategy  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | 10,804 | 33.7% | -0.216 | [-0.24, -0.19] | -1.01 | 0.69 | 31%/64%/4% | 13.1 |
| S2_Breakout | 923 | 25.0% | -0.214 | [-0.31, -0.12] | -1.01 | 0.73 | 23%/74%/3% | 9.9 |
| S3_Momentum | 16,613 | 33.0% | -0.238 | [-0.25, -0.22] | -1.00 | 0.61 | 16%/54%/28% | 25.2 |
| S4_MTF | 2,836 | 35.8% | -0.214 | [-0.25, -0.18] | -0.41 | 0.57 | 8%/38%/53% | 32.7 |

## 10. Time-stop diagnostic (deployed set)

TIME exits: n=748, mean R = +0.395, mean MFE = +0.95 R, share that reached ≥ +1 R at some point = 46%, mean MAE = -0.49 R.

A large MFE with a small final R says the target is too far for the horizon; a small MFE says the setup simply did not move.
