# Slot-capped portfolio comparison

Same per-symbol trade lists as phase3_simulation.md, admitted through a concurrent-position cap with priority S1 > S4 > S3. R net of costs.

## SWING

| cap | system | trades | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | v2 all | 902 | +0.117 | 52% | 1.29 | +0.83 | +9.6 | -7.2 | -24.5 | {'S3_Momentum': 579, 'S4_MTF': 299, 'S2_Breakout': 20, 'S1_MeanRev': 4} |
| 5 | v2 test | 485 | +0.071 | 49% | 1.16 | +0.55 | +6.1 | -5.9 | -24.5 | {'S3_Momentum': 320, 'S4_MTF': 157, 'S2_Breakout': 7, 'S1_MeanRev': 1} |
| 5 | v3 all | 690 | +0.160 | 54% | 1.33 | +0.83 | +9.9 | -8.3 | -17.2 | {'S3_Momentum': 418, 'S4_MTF': 211, 'S1_MeanRev': 61} |
| 5 | v3 test | 354 | +0.162 | 53% | 1.33 | +0.81 | +10.1 | -8.3 | -17.2 | {'S3_Momentum': 211, 'S4_MTF': 113, 'S1_MeanRev': 30} |
| 10 | v2 all | 1,223 | +0.138 | 54% | 1.35 | +1.00 | +15.3 | -10.0 | -22.5 | {'S3_Momentum': 815, 'S4_MTF': 374, 'S2_Breakout': 27, 'S1_MeanRev': 7} |
| 10 | v2 test | 667 | +0.086 | 51% | 1.20 | +0.69 | +10.1 | -6.2 | -22.5 | {'S3_Momentum': 455, 'S4_MTF': 202, 'S2_Breakout': 9, 'S1_MeanRev': 1} |
| 10 | v3 all | 1,298 | +0.184 | 54% | 1.38 | +1.11 | +21.5 | -13.0 | -30.1 | {'S3_Momentum': 845, 'S4_MTF': 357, 'S1_MeanRev': 96} |
| 10 | v3 test | 686 | +0.131 | 52% | 1.26 | +0.83 | +15.8 | -12.4 | -25.5 | {'S3_Momentum': 448, 'S4_MTF': 187, 'S1_MeanRev': 51} |
| 20 | v2 all | 1,354 | +0.143 | 54% | 1.36 | +1.04 | +17.5 | -10.0 | -30.2 | {'S3_Momentum': 928, 'S4_MTF': 389, 'S2_Breakout': 30, 'S1_MeanRev': 7} |
| 20 | v2 test | 729 | +0.090 | 51% | 1.21 | +0.71 | +11.5 | -6.4 | -30.2 | {'S3_Momentum': 507, 'S4_MTF': 211, 'S2_Breakout': 10, 'S1_MeanRev': 1} |
| 20 | v3 all | 2,313 | +0.214 | 55% | 1.46 | +1.31 | +44.5 | -33.5 | -38.9 | {'S3_Momentum': 1634, 'S4_MTF': 533, 'S1_MeanRev': 146} |
| 20 | v3 test | 1,215 | +0.193 | 53% | 1.41 | +1.25 | +41.3 | -15.7 | -38.9 | {'S3_Momentum': 870, 'S4_MTF': 267, 'S1_MeanRev': 78} |
| ∞ | v2 all | 1,355 | +0.142 | 54% | 1.36 | +1.03 | +17.4 | -10.0 | -31.2 | {'S3_Momentum': 928, 'S4_MTF': 389, 'S2_Breakout': 31, 'S1_MeanRev': 7} |
| ∞ | v2 test | 730 | +0.088 | 51% | 1.21 | +0.69 | +11.3 | -6.7 | -31.2 | {'S3_Momentum': 507, 'S4_MTF': 211, 'S2_Breakout': 11, 'S1_MeanRev': 1} |
| ∞ | v3 all | 3,283 | +0.232 | 56% | 1.51 | +1.40 | +68.5 | -37.4 | -63.4 | {'S3_Momentum': 2522, 'S4_MTF': 606, 'S1_MeanRev': 155} |
| ∞ | v3 test | 1,704 | +0.207 | 54% | 1.44 | +1.29 | +62.0 | -19.8 | -56.7 | {'S3_Momentum': 1315, 'S4_MTF': 309, 'S1_MeanRev': 80} |

## POSITIONAL

| cap | system | trades | mean R | hit | PF | SR ann | R per year | worst month | max DD (R) | mix |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | v2 all | 406 | +0.237 | 55% | 1.64 | +1.11 | +8.7 | -6.1 | -11.3 | {'S3_Momentum': 198, 'S4_MTF': 196, 'S2_Breakout': 11, 'S1_MeanRev': 1} |
| 5 | v2 test | 214 | +0.151 | 50% | 1.38 | +0.86 | +5.7 | -6.1 | -11.3 | {'S4_MTF': 109, 'S3_Momentum': 103, 'S2_Breakout': 2} |
| 5 | v3 all | 310 | +0.178 | 55% | 1.41 | +0.79 | +5.0 | -6.5 | -15.5 | {'S3_Momentum': 171, 'S4_MTF': 115, 'S1_MeanRev': 24} |
| 5 | v3 test | 156 | +0.117 | 52% | 1.25 | +0.52 | +3.2 | -5.2 | -15.5 | {'S3_Momentum': 85, 'S4_MTF': 60, 'S1_MeanRev': 11} |
| 10 | v2 all | 772 | +0.248 | 55% | 1.67 | +1.32 | +17.4 | -8.1 | -21.5 | {'S3_Momentum': 401, 'S4_MTF': 356, 'S2_Breakout': 14, 'S1_MeanRev': 1} |
| 10 | v2 test | 416 | +0.183 | 52% | 1.46 | +1.10 | +13.5 | -7.0 | -21.5 | {'S3_Momentum': 221, 'S4_MTF': 193, 'S2_Breakout': 2} |
| 10 | v3 all | 609 | +0.155 | 54% | 1.35 | +0.79 | +8.5 | -10.0 | -29.8 | {'S3_Momentum': 370, 'S4_MTF': 197, 'S1_MeanRev': 42} |
| 10 | v3 test | 322 | +0.106 | 52% | 1.22 | +0.55 | +6.1 | -8.0 | -29.8 | {'S3_Momentum': 205, 'S4_MTF': 98, 'S1_MeanRev': 19} |
| 20 | v2 all | 1,238 | +0.281 | 57% | 1.76 | +1.54 | +31.5 | -9.9 | -35.6 | {'S3_Momentum': 709, 'S4_MTF': 499, 'S2_Breakout': 27, 'S1_MeanRev': 3} |
| 20 | v2 test | 668 | +0.240 | 54% | 1.62 | +1.37 | +28.3 | -8.7 | -35.6 | {'S3_Momentum': 389, 'S4_MTF': 269, 'S2_Breakout': 10} |
| 20 | v3 all | 1,165 | +0.218 | 57% | 1.51 | +1.13 | +22.8 | -21.0 | -45.8 | {'S3_Momentum': 764, 'S4_MTF': 336, 'S1_MeanRev': 65} |
| 20 | v3 test | 611 | +0.187 | 55% | 1.42 | +1.00 | +20.2 | -14.1 | -45.8 | {'S3_Momentum': 407, 'S4_MTF': 171, 'S1_MeanRev': 33} |
| ∞ | v2 all | 1,401 | +0.255 | 56% | 1.67 | +1.43 | +32.3 | -10.7 | -41.6 | {'S3_Momentum': 839, 'S4_MTF': 526, 'S2_Breakout': 33, 'S1_MeanRev': 3} |
| ∞ | v2 test | 747 | +0.199 | 53% | 1.49 | +1.12 | +26.2 | -10.7 | -41.6 | {'S3_Momentum': 455, 'S4_MTF': 280, 'S2_Breakout': 12} |
| ∞ | v3 all | 1,975 | +0.276 | 61% | 1.70 | +1.41 | +49.2 | -27.3 | -73.1 | {'S3_Momentum': 1461, 'S4_MTF': 442, 'S1_MeanRev': 72} |
| ∞ | v3 test | 1,023 | +0.230 | 58% | 1.55 | +1.24 | +41.6 | -15.3 | -73.1 | {'S3_Momentum': 767, 'S4_MTF': 221, 'S1_MeanRev': 35} |
