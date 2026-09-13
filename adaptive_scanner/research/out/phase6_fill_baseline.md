# Phase 6 — deployable baseline: v3 filled at the next open vs at the signal close

Same trade generation as phase3_final.md (Pine defaults, sequential per symbol, EXITS_V3, 3 bps per leg). `close` = fill at the signal close (harness convention). `next_open` = fill at the next session's open against the engine's absolute stop, which is what the webhook → server path can actually execute. Paired on identical signals.

## SWING

| cap | fill | split | trades | mean R | hit | PF | SR ann | R per year | max DD (R) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | close | all | 1,179 | +0.215 | 55% | 1.46 | +1.12 | +22.9 | -27.3 |
| 10 | close | test 2021+ | 619 | +0.216 | 54% | 1.45 | +1.21 | +23.6 | -19.1 |
| 10 | next_open | all | 1,138 | +0.220 | 55% | 1.47 | +1.12 | +22.6 | -21.5 |
| 10 | next_open | test 2021+ | 602 | +0.205 | 53% | 1.42 | +1.05 | +21.7 | -21.5 |
| ∞ | close | all | 2,304 | +0.263 | 57% | 1.59 | +1.42 | +54.5 | -42.6 |
| ∞ | close | test 2021+ | 1,207 | +0.238 | 55% | 1.52 | +1.36 | +50.7 | -39.5 |
| ∞ | next_open | all | 2,263 | +0.245 | 57% | 1.54 | +1.33 | +49.9 | -43.2 |
| ∞ | next_open | test 2021+ | 1,188 | +0.224 | 55% | 1.48 | +1.23 | +47.0 | -43.2 |

**Paired next_open − close, uncapped, n = 2,204: -0.022 R per trade, 95% CI [-0.046, +0.001]; test 2021+: -0.032.**

| strategy | n | mean R close | mean R next_open | Δ |
|---|---:|---:|---:|---:|
| S1_MeanRev | 142 | +0.515 | +0.408 | -0.108 |
| S3_Momentum | 1,460 | +0.248 | +0.234 | -0.015 |
| S4_MTF | 602 | +0.267 | +0.246 | -0.021 |

**DSR, SWING next_open at cap 10 (monthly units):**

| N trials | DSR | MinTRL (months) |
|---:|---:|---:|
| 100 | **0.561** | 25 |
| 500 | **0.274** | 25 |
| 2000 | **0.120** | 25 |

## POSITIONAL

| cap | fill | split | trades | mean R | hit | PF | SR ann | R per year | max DD (R) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 10 | close | all | 383 | +0.301 | 63% | 1.82 | +1.36 | +10.4 | -10.9 |
| 10 | close | test 2021+ | 194 | +0.263 | 62% | 1.71 | +1.27 | +9.0 | -10.9 |
| 10 | next_open | all | 347 | +0.272 | 62% | 1.72 | +1.23 | +8.6 | -11.5 |
| 10 | next_open | test 2021+ | 174 | +0.259 | 61% | 1.68 | +1.14 | +8.0 | -11.5 |
| ∞ | close | all | 591 | +0.340 | 65% | 1.98 | +1.51 | +18.2 | -14.3 |
| ∞ | close | test 2021+ | 298 | +0.295 | 63% | 1.83 | +1.46 | +15.5 | -8.7 |
| ∞ | next_open | all | 582 | +0.334 | 65% | 1.96 | +1.51 | +17.6 | -12.6 |
| ∞ | next_open | test 2021+ | 297 | +0.289 | 63% | 1.81 | +1.43 | +15.2 | -10.2 |

**Paired next_open − close, uncapped, n = 571: -0.008 R per trade, 95% CI [-0.035, +0.020]; test 2021+: -0.025.**

| strategy | n | mean R close | mean R next_open | Δ |
|---|---:|---:|---:|---:|
| S4_MTF | 571 | +0.340 | +0.332 | -0.008 |

**DSR, POSITIONAL next_open at cap 10 (monthly units):**

| N trials | DSR | MinTRL (months) |
|---:|---:|---:|
| 100 | **0.677** | 24 |
| 500 | **0.420** | 24 |
| 2000 | **0.241** | 24 |
