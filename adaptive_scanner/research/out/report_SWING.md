# Phase 2 validation — profile SWING

Universe: 48 symbols, 2015-07-28 → 2026-09-10 (11.1 years). Trigger events: 59,951 (28,775 long). Deployed (fired): 1,543 = 2.89 per symbol-year.

R is in units of initial risk; headline column is `R_net3` (3 bps round-trip). **Survivorship caveat:** the universe is today's liquid names, so long-side baselines are optimistic.

## 1. Deployed set (what the scanner would actually have fired)

| strategy  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | 7 | 42.9% | -0.369 | [-2.44, +1.70] | -1.01 | 0.67 | 29%/57%/14% | 5.4 |
| S2_Breakout | 33 | 39.4% | +0.018 | [-0.52, +0.56] | -1.01 | 1.03 | 3%/61%/36% | 6.2 |
| S3_Momentum | 1,081 | 52.6% | +0.141 | [+0.07, +0.21] | +0.11 | 1.34 | 19%/35%/46% | 8.0 |
| S4_MTF | 422 | 58.8% | +0.193 | [+0.10, +0.28] | +0.21 | 1.64 | 13%/22%/64% | 9.0 |
| **ALL** | 1,543 | 54.0% | +0.150 | [+0.10, +0.20] | +0.13 | 1.38 | 17%/32%/51% | 8.2 |

Exit-reason split is TP / SL / TIME. A TIME share near 50% means the horizon, not the thesis, is deciding most trades.

## 2. Ablation baseline — every long trigger event, no score filter

If the deployed row is not clearly better than this, the score is not adding anything the trigger did not already have.

| strategy | population  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | all triggers | 3,516 | 46.9% | +0.248 | [+0.20, +0.30] | -0.55 | 1.44 | 18%/49%/33% | 6.4 |
| S1_MeanRev | aligned only | 350 | 43.1% | +0.131 | [-0.04, +0.30] | -1.01 | 1.21 | 24%/53%/23% | 6.0 |
| S1_MeanRev | aligned, score ≥ min | 16 | 62.5% | +0.354 | [-0.63, +1.33] | +0.76 | 1.57 | 31%/38%/31% | 6.6 |
| S2_Breakout | all triggers | 491 | 36.0% | +0.078 | [-0.08, +0.23] | -1.01 | 1.11 | 11%/62%/27% | 5.8 |
| S2_Breakout | aligned only | 296 | 36.1% | +0.078 | [-0.12, +0.27] | -1.01 | 1.12 | 9%/61%/30% | 6.0 |
| S2_Breakout | aligned, score ≥ min | 42 | 40.5% | +0.023 | [-0.45, +0.50] | -1.01 | 1.03 | 2%/60%/38% | 6.3 |
| S3_Momentum | all triggers | 16,762 | 53.0% | +0.145 | [+0.13, +0.16] | +0.12 | 1.35 | 20%/35%/45% | 8.0 |
| S3_Momentum | aligned only | 7,361 | 53.2% | +0.155 | [+0.13, +0.18] | +0.14 | 1.38 | 19%/35%/46% | 8.1 |
| S3_Momentum | aligned, score ≥ min | 1,785 | 52.0% | +0.149 | [+0.10, +0.20] | +0.08 | 1.36 | 19%/35%/46% | 8.0 |
| S4_MTF | all triggers | 8,006 | 55.9% | +0.132 | [+0.11, +0.15] | +0.15 | 1.41 | 11%/25%/64% | 9.0 |
| S4_MTF | aligned only | 2,954 | 57.2% | +0.153 | [+0.12, +0.19] | +0.18 | 1.49 | 11%/24%/64% | 9.0 |
| S4_MTF | aligned, score ≥ min | 507 | 60.0% | +0.223 | [+0.14, +0.31] | +0.23 | 1.77 | 14%/21%/65% | 8.9 |

## 3. Does the score predict outcome? Expectancy by score decile (long trigger events, within strategy)

**S1_MeanRev** — n=3,516, Spearman(score, R) = -0.013 (p=0.44), decile monotonicity = +0.10

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 21–26 | 352 | 53.1% | +0.381 |
| 2 | 26–34 | 352 | 48.3% | +0.270 |
| 3 | 34–36 | 351 | 44.7% | +0.102 |
| 4 | 36–41 | 352 | 49.4% | +0.399 |
| 5 | 41–42 | 351 | 41.9% | +0.032 |
| 6 | 42–47 | 352 | 50.0% | +0.294 |
| 7 | 47–49 | 351 | 41.0% | +0.126 |
| 8 | 49–54 | 352 | 44.3% | +0.138 |
| 9 | 54–59 | 351 | 45.3% | +0.344 |
| 10 | 59–82 | 352 | 51.1% | +0.397 |

**S2_Breakout** — n=491, Spearman(score, R) = -0.039 (p=0.39), decile monotonicity = -0.43

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 20–34 | 50 | 38.0% | +0.128 |
| 2 | 34–38 | 49 | 30.6% | +0.073 |
| 3 | 39–42 | 49 | 36.7% | +0.279 |
| 4 | 42–45 | 49 | 34.7% | -0.071 |
| 5 | 45–50 | 49 | 32.7% | +0.150 |
| 6 | 50–52 | 49 | 46.9% | +0.382 |
| 7 | 52–57 | 49 | 26.5% | -0.138 |
| 8 | 57–62 | 49 | 38.8% | +0.104 |
| 9 | 62–74 | 49 | 34.7% | -0.156 |
| 10 | 74–100 | 49 | 40.8% | +0.028 |

**S3_Momentum** — n=16,762, Spearman(score, R) = +0.015 (p=0.048), decile monotonicity = +0.35

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 6–35 | 1,677 | 49.5% | +0.087 |
| 2 | 35–48 | 1,676 | 51.6% | +0.117 |
| 3 | 48–56 | 1,676 | 51.7% | +0.094 |
| 4 | 56–60 | 1,676 | 54.1% | +0.194 |
| 5 | 60–64 | 1,676 | 56.0% | +0.232 |
| 6 | 64–66 | 1,676 | 54.5% | +0.165 |
| 7 | 66–69 | 1,676 | 51.0% | +0.097 |
| 8 | 69–74 | 1,676 | 56.2% | +0.164 |
| 9 | 74–79 | 1,676 | 53.0% | +0.165 |
| 10 | 79–100 | 1,677 | 52.5% | +0.133 |

**S4_MTF** — n=8,006, Spearman(score, R) = +0.063 (p=1.8e-08), decile monotonicity = +0.55

| decile | score range | n | hit | mean R |
|---:|:---:|---:|---:|---:|
| 1 | 27–48 | 801 | 49.1% | -0.023 |
| 2 | 49–53 | 801 | 53.3% | +0.064 |
| 3 | 53–57 | 800 | 51.1% | +0.059 |
| 4 | 57–59 | 801 | 58.3% | +0.184 |
| 5 | 59–63 | 800 | 56.8% | +0.168 |
| 6 | 63–67 | 801 | 57.1% | +0.177 |
| 7 | 67–69 | 800 | 59.4% | +0.170 |
| 8 | 69–73 | 801 | 54.9% | +0.109 |
| 9 | 73–78 | 800 | 61.5% | +0.256 |
| 10 | 78–92 | 801 | 57.4% | +0.160 |

## 4. Walk-forward: does the score→expectancy map hold out of sample?

Rolling 3-year train / 1-year test. Fit a quintile→mean-R map on train, apply to test, report Spearman(predicted, realised).

| strategy | folds | mean OOS ρ | folds with ρ>0 | mean(top − bottom quintile R) |
|---|---:|---:|---:|---:|
| S1_MeanRev | 9 | -0.001 | 56% | -0.036 |
| S2_Breakout | 7 | -0.004 | 71% | -0.214 |
| S3_Momentum | 9 | +0.002 | 56% | +0.005 |
| S4_MTF | 9 | +0.046 | 56% | +0.189 |

<details><summary>S1_MeanRev folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 657.0 | 487.0 | -0.07 | 0.15 | +0.18 | +0.45 | +0.20 |
| 2019.0 | 966.0 | 217.0 | -0.02 | 0.80 | +0.28 | +0.50 | +0.47 |
| 2020.0 | 819.0 | 355.0 | +0.06 | 0.25 | -0.45 | -0.23 | -0.35 |
| 2021.0 | 1,060.0 | 194.0 | -0.10 | 0.16 | +0.51 | +0.61 | +0.58 |
| 2022.0 | 767.0 | 514.0 | +0.00 | 0.92 | +0.46 | +0.06 | +0.21 |
| 2023.0 | 1,063.0 | 313.0 | +0.04 | 0.52 | +0.20 | +0.13 | +0.21 |
| 2024.0 | 1,022.0 | 285.0 | +0.02 | 0.76 | +0.53 | +0.52 | +0.47 |
| 2025.0 | 1,113.0 | 310.0 | +0.07 | 0.23 | +0.38 | +0.45 | +0.51 |
| 2026.0 | 909.0 | 182.0 | -0.01 | 0.91 | +0.75 | +0.67 | +0.49 |

</details>

<details><summary>S2_Breakout folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019.0 | 114.0 | 63.0 | +0.08 | 0.56 | +0.23 | +0.43 | +0.38 |
| 2020.0 | 140.0 | 36.0 | -0.30 | 0.07 | -0.22 | +0.88 | -0.07 |
| 2021.0 | 141.0 | 48.0 | +0.10 | 0.50 | -0.01 | -0.37 | +0.03 |
| 2022.0 | 148.0 | 59.0 | +0.08 | 0.56 | +0.50 | +0.35 | +0.18 |
| 2023.0 | 143.0 | 55.0 | +0.08 | 0.58 | -0.33 | +0.03 | -0.09 |
| 2024.0 | 162.0 | 33.0 | +0.11 | 0.54 | -0.07 | +0.32 | +0.51 |
| 2025.0 | 147.0 | 30.0 | -0.16 | 0.40 | -0.16 | -0.19 | -0.44 |

</details>

<details><summary>S3_Momentum folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 3,533.0 | 1,566.0 | -0.00 | 0.86 | +0.01 | -0.08 | -0.09 |
| 2019.0 | 4,414.0 | 1,590.0 | -0.03 | 0.27 | +0.22 | +0.40 | +0.33 |
| 2020.0 | 4,532.0 | 1,430.0 | +0.02 | 0.40 | +0.15 | +0.11 | +0.16 |
| 2021.0 | 4,586.0 | 1,617.0 | +0.00 | 0.90 | +0.32 | +0.08 | +0.23 |
| 2022.0 | 4,637.0 | 1,474.0 | +0.03 | 0.32 | +0.02 | -0.05 | -0.00 |
| 2023.0 | 4,521.0 | 1,524.0 | +0.11 | 0.00 | +0.19 | -0.04 | +0.16 |
| 2024.0 | 4,615.0 | 1,371.0 | -0.07 | 0.01 | -0.07 | +0.42 | +0.11 |
| 2025.0 | 4,369.0 | 1,617.0 | +0.05 | 0.06 | -0.09 | +0.05 | +0.07 |
| 2026.0 | 4,512.0 | 1,040.0 | -0.08 | 0.01 | +0.20 | +0.02 | +0.08 |

</details>

<details><summary>S4_MTF folds</summary>

| test year | n train | n test | OOS ρ | p | top R | bottom R | all R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018.0 | 1,754.0 | 789.0 | -0.01 | 0.77 | +0.04 | -0.07 | +0.02 |
| 2019.0 | 2,366.0 | 608.0 | +0.06 | 0.13 | +0.27 | +0.06 | +0.18 |
| 2020.0 | 2,296.0 | 774.0 | -0.02 | 0.60 | +0.23 | +0.06 | +0.16 |
| 2021.0 | 2,171.0 | 968.0 | -0.05 | 0.09 | +0.30 | +0.10 | +0.20 |
| 2022.0 | 2,350.0 | 420.0 | -0.03 | 0.53 | -0.17 | -0.06 | -0.17 |
| 2023.0 | 2,162.0 | 582.0 | +0.12 | 0.00 | +0.26 | -0.07 | +0.15 |
| 2024.0 | 1,970.0 | 915.0 | +0.02 | 0.60 | +0.14 | +0.05 | +0.16 |
| 2025.0 | 1,917.0 | 601.0 | +0.16 | 0.00 | +0.43 | +0.08 | +0.28 |
| 2026.0 | 2,099.0 | 594.0 | +0.17 | 0.00 | +0.17 | -0.19 | +0.05 |

</details>

## 5. Strategy × regime expectancy (long trigger events, aligned only)

| strategy | NEUTRAL | MEAN_REV | BREAKOUT | MOMENTUM | TRENDING |
|---|---:|---:|---:|---:|---:|
| S1_MeanRev | +0.14 (n=335) | — (n=15) | — (n=0) | — (n=0) | — (n=0) |
| S2_Breakout | +0.13 (n=213) | — (n=0) | +0.02 (n=71) | — (n=0) | — (n=12) |
| S3_Momentum | +0.15 (n=6,139) | — (n=0) | — (n=0) | +0.20 (n=1,166) | -0.11 (n=56) |
| S4_MTF | +0.15 (n=2,825) | — (n=0) | — (n=0) | — (n=0) | +0.26 (n=129) |

The alignment filter makes most cells structurally empty: S1 only trades in MEAN_REV/NEUTRAL, S4 only in TRENDING/NEUTRAL.

## 6. Component ablation — which rubric parts carry the signal?

ρ = Spearman of the component alone vs R. Top-quartile expectancy re-selected by the score WITHOUT that component; Δ vs the full score. A negative Δ means the component was helping.

**S1_MeanRev**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | -0.013 | +0.267 | +0.000 | 1,284 |
| − trend | +0.040 | +0.203 | -0.064 | 938 |
| − mom | +0.052 | +0.260 | -0.007 | 1,183 |
| − loc | -0.025 | +0.304 | +0.037 | 1,201 |
| − vol | -0.057 | +0.380 | +0.113 | 1,024 |
| − htf | -0.035 | +0.281 | +0.014 | 1,201 |

**S2_Breakout**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | -0.039 | -0.053 | +0.000 | 158 |
| − trend | -0.060 | -0.157 | -0.104 | 130 |
| − mom | +0.032 | +0.039 | +0.092 | 175 |
| − loc | -0.086 | +0.104 | +0.157 | 123 |
| − vol | +0.030 | -0.096 | -0.043 | 125 |
| − htf | +0.009 | +0.014 | +0.067 | 190 |

**S3_Momentum**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | +0.015 | +0.149 | +0.000 | 4,334 |
| − trend | -0.020 | +0.162 | +0.013 | 4,196 |
| − mom | +0.014 | +0.172 | +0.023 | 5,959 |
| − loc | +0.032 | +0.121 | -0.028 | 4,443 |
| − vol | -0.002 | +0.135 | -0.014 | 4,496 |
| − htf | +0.019 | +0.164 | +0.016 | 4,377 |

**S4_MTF**

| component | ρ vs R | top-25% mean R | Δ | n |
|---|---:|---:|---:|---:|
| (full score) | +0.063 | +0.198 | +0.000 | 2,077 |
| − trend | +0.050 | +0.182 | -0.016 | 2,058 |
| − mom | +0.064 | +0.192 | -0.005 | 2,238 |
| − loc | +0.060 | +0.160 | -0.038 | 2,396 |
| − vol | -0.006 | +0.179 | -0.019 | 2,170 |
| − htf | +0.005 | +0.185 | -0.013 | 2,298 |

## 7. Cost sensitivity (deployed set)

| round-trip bps | S1_MeanRev | S2_Breakout | S3_Momentum | S4_MTF | ALL |
|---:|---:|---:|---:|---:|---:|
| 0 | -0.356 | +0.033 | +0.149 | +0.200 | +0.158 |
| 1 | -0.360 | +0.028 | +0.146 | +0.198 | +0.156 |
| 3 | -0.369 | +0.018 | +0.141 | +0.193 | +0.150 |
| 5 | -0.378 | +0.009 | +0.135 | +0.189 | +0.145 |
| 10 | -0.400 | -0.016 | +0.121 | +0.177 | +0.131 |

## 8. Multiple-testing corrections

**Deployed set:** per-trade SR = +0.139 over 1,543 trades; monthly SR (sum of R per month) = +0.317 over 135 months.

**Deflated Sharpe** (Bailey & López de Prado), monthly units. N = number of configurations the selection is assumed to have searched. The 56 here are only the ones this harness enumerated; the hand-tuned weights, thresholds and ATR multiples were chosen over an unknown, larger N, so read the row for N=500 as the honest one.

| N trials | E[max SR | null] | DSR | MinTRL (months) |
|---:|---:|---:|---:|
| 56 | +0.285 | **0.660** | 22 |
| 200 | +0.340 | **0.378** | 22 |
| 500 | +0.375 | **0.219** | 22 |
| 2000 | +0.424 | **0.079** | 22 |

**PBO via CSCV** over 56 (strategy × threshold × alignment) configurations on 135 monthly periods, S=16 blocks: **PBO = 0.20** (mean logit +0.56). Reject the configuration family if PBO > 0.5.

Best in-sample configurations by monthly Sharpe:

| configuration | monthly SR | months active |
|---|---:|---:|
| S4_MTF|>=60|aligned | +0.372 | 131 |
| S4_MTF|>=60|any | +0.352 | 134 |
| S4_MTF|>=50|any | +0.350 | 134 |
| S4_MTF|>=0|aligned | +0.349 | 132 |
| S4_MTF|>=50|aligned | +0.349 | 132 |
| S4_MTF|>=70|any | +0.334 | 129 |
| S4_MTF|>=70|aligned | +0.328 | 121 |
| S1_MeanRev|>=0|any | +0.323 | 127 |

## 9. Short-side trigger events (not deployed; informational)

| strategy  n | hit | mean R | 95% CI | med R | PF | TP/SL/TIME | bars |
|---:|---:|---:|:---:|---:|---:|:---:|---:|
| S1_MeanRev | 10,804 | 31.0% | -0.194 | [-0.22, -0.17] | -1.01 | 0.73 | 16%/63%/21% | 5.7 |
| S2_Breakout | 923 | 25.0% | -0.193 | [-0.31, -0.08] | -1.02 | 0.76 | 11%/72%/17% | 4.7 |
| S3_Momentum | 16,613 | 39.4% | -0.119 | [-0.13, -0.10] | -0.49 | 0.78 | 17%/45%/38% | 7.4 |
| S4_MTF | 2,836 | 39.4% | -0.153 | [-0.18, -0.12] | -0.27 | 0.65 | 7%/30%/63% | 9.1 |

## 10. Time-stop diagnostic (deployed set)

TIME exits: n=780, mean R = +0.386, mean MFE = +0.93 R, share that reached ≥ +1 R at some point = 43%, mean MAE = -0.47 R.

A large MFE with a small final R says the target is too far for the horizon; a small MFE says the setup simply did not move.
