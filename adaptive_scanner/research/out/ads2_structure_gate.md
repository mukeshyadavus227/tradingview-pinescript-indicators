# ADS2 v2.3.0 — swing structure gate, OFF vs ON

Deployed SWING profile (ASR v3 mirror: S1 > S4 > S3, EXITS_V3), 48 symbols, daily bars 2015-08-03 → 2026-09-11, sequential one position per symbol, fill at the next open against the absolute stop, R net of 3 bps per leg. Gate = close > SMA200 AND GR Trend Template ≥ k on S3/S4 signals (S1 never gated). Pine default = `ON S3+S4 tt3`. Portfolio = slot cap 10, priority S1 > S4 > S3.

**Regression check:** OFF at cap 10 = 1,138 trades, +0.220 R; phase6_fill_baseline = 1138 trades, +0.220 R → IDENTICAL.

## Portfolio, cap 10

**all**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 1,138 | 55% | +0.220 | 1.47 | +1.12 | +22.6 | -21.5 |
| ON S3+S4 tt3 | 1,011 | 55% | +0.209 | 1.45 | +1.07 | +19.2 | -24.2 |
| ON S3 only tt3 | 1,013 | 55% | +0.207 | 1.45 | +1.08 | +19.0 | -19.6 |
| ON S3+S4 tt0 | 1,065 | 54% | +0.196 | 1.41 | +1.01 | +18.8 | -18.3 |
| ON S3+S4 tt1 | 1,066 | 54% | +0.191 | 1.40 | +1.00 | +18.3 | -18.9 |
| ON S3+S4 tt2 | 1,041 | 54% | +0.187 | 1.40 | +0.99 | +17.6 | -20.0 |
| ON S3+S4 tt4 | 977 | 54% | +0.210 | 1.45 | +1.06 | +18.6 | -20.0 |
| ON S3+S4 tt5 | 852 | 52% | +0.234 | 1.48 | +1.02 | +18.0 | -19.3 |

**2015–2020 (pre-split)**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 536 | 57% | +0.238 | 1.52 | +1.18 | +23.6 | -17.4 |
| ON S3+S4 tt3 | 480 | 56% | +0.218 | 1.49 | +1.05 | +19.6 | -17.6 |
| ON S3 only tt3 | 481 | 56% | +0.208 | 1.46 | +1.00 | +18.8 | -17.4 |
| ON S3+S4 tt0 | 502 | 57% | +0.219 | 1.47 | +1.04 | +20.3 | -17.4 |
| ON S3+S4 tt1 | 505 | 56% | +0.207 | 1.45 | +1.00 | +19.4 | -18.9 |
| ON S3+S4 tt2 | 496 | 57% | +0.215 | 1.48 | +1.06 | +19.7 | -18.0 |
| ON S3+S4 tt4 | 464 | 57% | +0.270 | 1.62 | +1.31 | +23.4 | -14.9 |
| ON S3+S4 tt5 | 391 | 56% | +0.310 | 1.69 | +1.34 | +22.7 | -19.3 |

**2021+ (harness test window)**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 602 | 53% | +0.205 | 1.42 | +1.05 | +21.7 | -21.5 |
| ON S3+S4 tt3 | 531 | 53% | +0.201 | 1.42 | +1.08 | +18.9 | -24.2 |
| ON S3 only tt3 | 532 | 54% | +0.206 | 1.44 | +1.15 | +19.4 | -19.6 |
| ON S3+S4 tt0 | 563 | 52% | +0.175 | 1.36 | +0.98 | +17.4 | -18.3 |
| ON S3+S4 tt1 | 561 | 52% | +0.176 | 1.37 | +0.99 | +17.5 | -18.3 |
| ON S3+S4 tt2 | 545 | 52% | +0.163 | 1.34 | +0.91 | +15.7 | -20.0 |
| ON S3+S4 tt4 | 513 | 52% | +0.156 | 1.32 | +0.81 | +14.2 | -20.0 |
| ON S3+S4 tt5 | 461 | 48% | +0.169 | 1.33 | +0.75 | +13.7 | -18.6 |

## Uncapped, sequential per symbol

**all**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 2,263 | 57% | +0.245 | 1.54 | +1.33 | +49.9 | -43.2 |
| ON S3+S4 tt3 | 1,652 | 56% | +0.227 | 1.50 | +1.16 | +33.9 | -37.5 |
| ON S3 only tt3 | 1,660 | 55% | +0.223 | 1.49 | +1.14 | +33.5 | -37.5 |
| ON S3+S4 tt0 | 1,893 | 56% | +0.248 | 1.54 | +1.28 | +42.2 | -37.5 |
| ON S3+S4 tt1 | 1,888 | 56% | +0.248 | 1.54 | +1.29 | +42.1 | -37.5 |
| ON S3+S4 tt2 | 1,782 | 55% | +0.224 | 1.49 | +1.18 | +35.9 | -37.5 |
| ON S3+S4 tt4 | 1,436 | 55% | +0.231 | 1.50 | +1.16 | +30.0 | -33.3 |
| ON S3+S4 tt5 | 994 | 52% | +0.218 | 1.45 | +0.98 | +19.7 | -21.8 |

**2015–2020 (pre-split)**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 1,075 | 59% | +0.268 | 1.62 | +1.43 | +53.2 | -37.5 |
| ON S3+S4 tt3 | 794 | 58% | +0.251 | 1.57 | +1.18 | +37.1 | -37.5 |
| ON S3 only tt3 | 800 | 57% | +0.244 | 1.55 | +1.15 | +36.4 | -37.5 |
| ON S3+S4 tt0 | 907 | 58% | +0.267 | 1.60 | +1.35 | +44.8 | -37.5 |
| ON S3+S4 tt1 | 906 | 58% | +0.266 | 1.60 | +1.34 | +44.6 | -37.5 |
| ON S3+S4 tt2 | 868 | 58% | +0.248 | 1.56 | +1.25 | +39.8 | -37.5 |
| ON S3+S4 tt4 | 670 | 58% | +0.265 | 1.60 | +1.23 | +33.1 | -33.3 |
| ON S3+S4 tt5 | 444 | 55% | +0.268 | 1.58 | +1.21 | +22.2 | -21.8 |

**2021+ (harness test window)**

| variant | trades | win rate | avg R | PF | SR ann | R per year | max DD (R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 1,188 | 55% | +0.224 | 1.48 | +1.23 | +47.0 | -43.2 |
| ON S3+S4 tt3 | 858 | 53% | +0.204 | 1.44 | +1.13 | +30.9 | -30.9 |
| ON S3 only tt3 | 860 | 53% | +0.203 | 1.43 | +1.12 | +30.7 | -30.9 |
| ON S3+S4 tt0 | 986 | 54% | +0.230 | 1.49 | +1.21 | +39.9 | -34.1 |
| ON S3+S4 tt1 | 982 | 54% | +0.231 | 1.49 | +1.22 | +39.9 | -34.1 |
| ON S3+S4 tt2 | 914 | 53% | +0.201 | 1.42 | +1.11 | +32.3 | -34.3 |
| ON S3+S4 tt4 | 766 | 53% | +0.201 | 1.42 | +1.07 | +27.2 | -26.4 |
| ON S3+S4 tt5 | 550 | 50% | +0.179 | 1.35 | +0.79 | +17.3 | -18.8 |

## What the default gate removes (OFF trade list, uncapped)

| group | trades | win rate | avg R | 95% CI avg R |
|---|---:|---:|---:|---|
| removed (S3/S4 failing the gate) | 683 | 60% | +0.314 | [+0.210, +0.427] |
| kept | 1,580 | 55% | +0.215 | [+0.151, +0.281] |
| removed S3 | 668 | 60% | +0.318 | [+0.209, +0.426] |
| removed S4 | 15 | 60% | +0.143 | [-0.636, +0.883] |

Removed − kept: +0.098 R per trade, 95% CI [-0.027, +0.229].

## Walk-forward (expanding window, yearly re-selection, cap 10)

Each test year uses the configuration whose monthly Sharpe was best on every earlier year. Candidates: OFF and the gate at k = 0…5. First test year needs three years of history.

| test year | chosen | OOS R (chosen) | OOS R (OFF) | OOS R (default gate) |
|---|---|---:|---:|---:|
| 2018 | ON S3+S4 tt5 | +1.9 | -11.5 | -17.1 |
| 2019 | ON S3+S4 tt5 | +18.9 | +34.8 | +40.7 |
| 2020 | ON S3+S4 tt5 | +6.6 | +16.3 | +19.5 |
| 2021 | ON S3+S4 tt5 | +18.6 | +15.9 | +20.2 |
| 2022 | ON S3+S4 tt4 | -4.8 | -1.4 | -4.8 |
| 2023 | ON S3+S4 tt5 | -1.6 | +28.7 | +22.2 |
| 2024 | ON S3+S4 tt4 | +37.5 | +30.2 | +34.8 |
| 2025 | ON S3+S4 tt4 | +4.7 | +30.6 | +12.5 |
| 2026 | OFF | +19.1 | +19.1 | +21.8 |

| stitched OOS | total R | SR ann | max DD (R) |
|---|---:|---:|---:|
| walk-forward choice | +100.8 | +0.62 | -29.8 |
| OFF | +162.7 | +0.94 | -21.5 |
| default gate (ON S3+S4 tt3) | +149.9 | +0.96 | -24.2 |

Paired monthly R, default gate − OFF (cap 10, 133 months): -0.30 R/month, 95% CI [-0.85, +0.22].

## Deflated Sharpe, cap 10, monthly units

| variant | SR (monthly) | DSR N=100 | DSR N=500 |
|---|---:|---:|---:|
| OFF | +0.323 | 0.561 | 0.274 |
| ON S3+S4 tt3 | +0.310 | 0.499 | 0.227 |
