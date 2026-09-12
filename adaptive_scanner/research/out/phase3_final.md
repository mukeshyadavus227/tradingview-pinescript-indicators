# Phase 3 — deployed v3 vs v2 (Pine defaults)

Per-symbol sequential (one position per chart), then a portfolio slot cap with priority S1 > S4 > S3. R net of 3 bps per leg. Test = entries 2021+.

## SWING

| cap | system | trades | /sym-yr | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | v2 all | 902 | 1.70 | +0.117 | 52% | 1.29 | +0.83 | +9.6 | -7.2 | -24.5 | {'S3_Momentum': 579, 'S4_MTF': 299, 'S2_Breakout': 20, 'S1_MeanRev': 4} |
| 5 | v2 test | 485 | 1.78 | +0.071 | 49% | 1.16 | +0.55 | +6.1 | -5.9 | -24.5 | {'S3_Momentum': 320, 'S4_MTF': 157, 'S2_Breakout': 7, 'S1_MeanRev': 1} |
| 5 | v3 all | 641 | 1.20 | +0.153 | 53% | 1.31 | +0.79 | +8.8 | -8.0 | -17.1 | {'S3_Momentum': 328, 'S4_MTF': 236, 'S1_MeanRev': 77} |
| 5 | v3 test | 343 | 1.26 | +0.132 | 52% | 1.26 | +0.76 | +8.0 | -6.7 | -17.1 | {'S3_Momentum': 184, 'S4_MTF': 123, 'S1_MeanRev': 36} |
| 10 | v2 all | 1,223 | 2.30 | +0.138 | 54% | 1.35 | +1.00 | +15.3 | -10.0 | -22.5 | {'S3_Momentum': 815, 'S4_MTF': 374, 'S2_Breakout': 27, 'S1_MeanRev': 7} |
| 10 | v2 test | 667 | 2.45 | +0.086 | 51% | 1.20 | +0.69 | +10.1 | -6.2 | -22.5 | {'S3_Momentum': 455, 'S4_MTF': 202, 'S2_Breakout': 9, 'S1_MeanRev': 1} |
| 10 | v3 all | 1,179 | 2.22 | +0.215 | 55% | 1.46 | +1.12 | +22.9 | -10.8 | -27.3 | {'S3_Momentum': 654, 'S4_MTF': 408, 'S1_MeanRev': 117} |
| 10 | v3 test | 619 | 2.28 | +0.216 | 54% | 1.45 | +1.21 | +23.6 | -9.3 | -19.1 | {'S3_Momentum': 350, 'S4_MTF': 209, 'S1_MeanRev': 60} |
| 20 | v2 all | 1,354 | 2.55 | +0.143 | 54% | 1.36 | +1.04 | +17.5 | -10.0 | -30.2 | {'S3_Momentum': 928, 'S4_MTF': 389, 'S2_Breakout': 30, 'S1_MeanRev': 7} |
| 20 | v2 test | 729 | 2.67 | +0.090 | 51% | 1.21 | +0.71 | +11.5 | -6.4 | -30.2 | {'S3_Momentum': 507, 'S4_MTF': 211, 'S2_Breakout': 10, 'S1_MeanRev': 1} |
| 20 | v3 all | 1,925 | 3.61 | +0.245 | 56% | 1.54 | +1.34 | +42.4 | -35.0 | -43.1 | {'S3_Momentum': 1189, 'S4_MTF': 584, 'S1_MeanRev': 152} |
| 20 | v3 test | 1,009 | 3.70 | +0.242 | 55% | 1.52 | +1.51 | +43.1 | -11.4 | -27.7 | {'S3_Momentum': 639, 'S4_MTF': 294, 'S1_MeanRev': 76} |
| ∞ | v2 all | 1,355 | 2.55 | +0.142 | 54% | 1.36 | +1.03 | +17.4 | -10.0 | -31.2 | {'S3_Momentum': 928, 'S4_MTF': 389, 'S2_Breakout': 31, 'S1_MeanRev': 7} |
| ∞ | v2 test | 730 | 2.68 | +0.088 | 51% | 1.21 | +0.69 | +11.3 | -6.7 | -31.2 | {'S3_Momentum': 507, 'S4_MTF': 211, 'S2_Breakout': 11, 'S1_MeanRev': 1} |
| ∞ | v3 all | 2,304 | 4.32 | +0.263 | 57% | 1.59 | +1.42 | +54.5 | -35.2 | -42.6 | {'S3_Momentum': 1512, 'S4_MTF': 639, 'S1_MeanRev': 153} |
| ∞ | v3 test | 1,207 | 4.43 | +0.238 | 55% | 1.52 | +1.36 | +50.7 | -11.6 | -39.5 | {'S3_Momentum': 804, 'S4_MTF': 326, 'S1_MeanRev': 77} |

**v3 SWING by strategy (uncapped):**

| strategy | trades | mean R | test R | hit | PF | bars | test exit reasons |
|---|---:|---:|---:|---:|---:|---:|---|
| S1_MeanRev | 153 | +0.434 | +0.569 | 48% | 1.84 | 7.2 | {'TIME': 0.58, 'SL': 0.31, 'SL_GAP': 0.05, 'TRAIL': 0.03, 'TRAIL_GAP': 0.01, 'EOD': 0.01} |
| S3_Momentum | 1,512 | +0.239 | +0.203 | 57% | 1.53 | 19.7 | {'SL': 0.36, 'TRAIL': 0.33, 'BE': 0.11, 'SL_GAP': 0.09, 'TRAIL_GAP': 0.07, 'BE_GAP': 0.03, 'EOD': 0.0} |
| S4_MTF | 639 | +0.277 | +0.248 | 60% | 1.66 | 24.2 | {'TRAIL': 0.43, 'SL': 0.34, 'TRAIL_GAP': 0.08, 'SL_GAP': 0.07, 'BE': 0.04, 'EOD': 0.03, 'BE_GAP': 0.01} |

**DSR, v3 SWING at cap 10 (monthly units; selection searched ~14 exit models × 7 rule variants):**

| N trials | E[max SR] | DSR | MinTRL (months) |
|---:|---:|---:|---:|
| 100 | +0.310 | **0.565** | 26 |
| 500 | +0.374 | **0.279** | 26 |
| 2000 | +0.422 | **0.124** | 26 |

## POSITIONAL

| cap | system | trades | /sym-yr | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | v2 all | 406 | 0.77 | +0.237 | 55% | 1.64 | +1.11 | +8.7 | -6.1 | -11.3 | {'S3_Momentum': 198, 'S4_MTF': 196, 'S2_Breakout': 11, 'S1_MeanRev': 1} |
| 5 | v2 test | 214 | 0.79 | +0.151 | 50% | 1.38 | +0.86 | +5.7 | -6.1 | -11.3 | {'S4_MTF': 109, 'S3_Momentum': 103, 'S2_Breakout': 2} |
| 5 | v3 all | 210 | 0.40 | +0.308 | 63% | 1.82 | +1.28 | +5.9 | -4.0 | -9.2 | {'S4_MTF': 210} |
| 5 | v3 test | 108 | 0.40 | +0.243 | 61% | 1.62 | +1.08 | +4.7 | -2.1 | -9.2 | {'S4_MTF': 108} |
| 10 | v2 all | 772 | 1.46 | +0.248 | 55% | 1.67 | +1.32 | +17.4 | -8.1 | -21.5 | {'S3_Momentum': 401, 'S4_MTF': 356, 'S2_Breakout': 14, 'S1_MeanRev': 1} |
| 10 | v2 test | 416 | 1.53 | +0.183 | 52% | 1.46 | +1.10 | +13.5 | -7.0 | -21.5 | {'S3_Momentum': 221, 'S4_MTF': 193, 'S2_Breakout': 2} |
| 10 | v3 all | 383 | 0.72 | +0.301 | 63% | 1.82 | +1.36 | +10.4 | -6.1 | -10.9 | {'S4_MTF': 383} |
| 10 | v3 test | 194 | 0.72 | +0.263 | 62% | 1.71 | +1.27 | +9.0 | -5.0 | -10.9 | {'S4_MTF': 194} |
| 20 | v2 all | 1,238 | 2.33 | +0.281 | 57% | 1.76 | +1.54 | +31.5 | -9.9 | -35.6 | {'S3_Momentum': 709, 'S4_MTF': 499, 'S2_Breakout': 27, 'S1_MeanRev': 3} |
| 20 | v2 test | 668 | 2.45 | +0.240 | 54% | 1.62 | +1.37 | +28.3 | -8.7 | -35.6 | {'S3_Momentum': 389, 'S4_MTF': 269, 'S2_Breakout': 10} |
| 20 | v3 all | 554 | 1.05 | +0.315 | 64% | 1.88 | +1.42 | +15.8 | -12.1 | -14.3 | {'S4_MTF': 554} |
| 20 | v3 test | 274 | 1.01 | +0.267 | 62% | 1.73 | +1.36 | +12.9 | -5.0 | -8.7 | {'S4_MTF': 274} |
| ∞ | v2 all | 1,401 | 2.64 | +0.255 | 56% | 1.67 | +1.43 | +32.3 | -10.7 | -41.6 | {'S3_Momentum': 839, 'S4_MTF': 526, 'S2_Breakout': 33, 'S1_MeanRev': 3} |
| ∞ | v2 test | 747 | 2.74 | +0.199 | 53% | 1.49 | +1.12 | +26.2 | -10.7 | -41.6 | {'S3_Momentum': 455, 'S4_MTF': 280, 'S2_Breakout': 12} |
| ∞ | v3 all | 591 | 1.12 | +0.340 | 65% | 1.98 | +1.51 | +18.2 | -12.1 | -14.3 | {'S4_MTF': 591} |
| ∞ | v3 test | 298 | 1.10 | +0.295 | 63% | 1.83 | +1.46 | +15.5 | -5.0 | -8.7 | {'S4_MTF': 298} |

**v3 POSITIONAL by strategy (uncapped):**

| strategy | trades | mean R | test R | hit | PF | bars | test exit reasons |
|---|---:|---:|---:|---:|---:|---:|---|
| S4_MTF | 591 | +0.340 | +0.295 | 65% | 1.98 | 54.3 | {'TRAIL': 0.49, 'SL': 0.3, 'TRAIL_GAP': 0.11, 'EOD': 0.05, 'SL_GAP': 0.04, 'BE': 0.0} |

**DSR, v3 POSITIONAL at cap 10 (monthly units; selection searched ~14 exit models × 7 rule variants):**

| N trials | E[max SR] | DSR | MinTRL (months) |
|---:|---:|---:|---:|
| 100 | +0.310 | **0.796** | 21 |
| 500 | +0.374 | **0.570** | 21 |
| 2000 | +0.422 | **0.377** | 21 |
