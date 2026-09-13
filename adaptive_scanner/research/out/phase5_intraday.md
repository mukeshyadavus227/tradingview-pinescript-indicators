# Phase 5 — INTRADAY_15M validation

48 symbols, 15m RTH bars 2025-12-08 → 2026-09-11; train < 2026-06-15 ≤ test. R net of 5 bps round trip unless stated. Trigger events: 22,727. **One regime only** — this can kill a strategy, not bless one.

## 1. Trigger vs eligible vs deployed, baseline exit (fixed 2R, EOD flat)

| population | n | mean R | hit | PF | SR/trade |
|---|---:|---:|---:|---:|---:|
| S5_ORB · all triggers · train | 2,499 | +0.012 | 46% | 1.03 | +0.012 |
| S5_ORB · eligible · train | 215 | +0.038 | 45% | 1.09 | +0.037 |
| S5_ORB · deployed · train | 215 | +0.038 | 45% | 1.09 | +0.037 |
| S5_ORB · all triggers · test | 1,189 | -0.189 | 38% | 0.64 | -0.192 |
| S5_ORB · eligible · test | 70 | -0.370 | 24% | 0.42 | -0.379 |
| S5_ORB · deployed · test | 70 | -0.370 | 24% | 0.42 | -0.379 |
| S6_VWAP_reclaim · all triggers · train | 5,464 | -0.124 | 40% | 0.78 | -0.109 |
| S6_VWAP_reclaim · eligible · train | 1,634 | -0.078 | 41% | 0.86 | -0.067 |
| S6_VWAP_reclaim · deployed · train | 1,630 | -0.077 | 41% | 0.86 | -0.067 |
| S6_VWAP_reclaim · all triggers · test | 2,708 | -0.212 | 36% | 0.65 | -0.194 |
| S6_VWAP_reclaim · eligible · test | 623 | -0.230 | 36% | 0.62 | -0.212 |
| S6_VWAP_reclaim · deployed · test | 622 | -0.228 | 36% | 0.63 | -0.211 |
| S3i_EMA_cross · all triggers · train | 7,460 | -0.057 | 44% | 0.88 | -0.054 |
| S3i_EMA_cross · eligible · train | 5,740 | -0.044 | 44% | 0.91 | -0.041 |
| S3i_EMA_cross · deployed · train | 5,600 | -0.046 | 44% | 0.90 | -0.043 |
| S3i_EMA_cross · all triggers · test | 3,407 | -0.284 | 34% | 0.52 | -0.290 |
| S3i_EMA_cross · eligible · test | 2,539 | -0.332 | 32% | 0.45 | -0.353 |
| S3i_EMA_cross · deployed · test | 2,501 | -0.330 | 32% | 0.46 | -0.350 |

## 2. Cost sensitivity (eligible, all periods, baseline exit)

| strategy | 0 bps | 2 bps | 5 bps | 10 bps |
|---|---:|---:|---:|---:|
| S5_ORB | +0.003 | -0.023 | -0.062 | -0.127 |
| S6_VWAP_reclaim | -0.008 | -0.053 | -0.120 | -0.231 |
| S3i_EMA_cross | -0.032 | -0.072 | -0.133 | -0.234 |

## 3. Exit models (eligible events)

| model | n train | n test | mean R train | mean R test | hit te | PF te | SR te | EOD% te | bars te |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **S5_ORB** | | | | | | | | | |
| I0_fixed2R_eod | 215 | 70 | +0.038 | **-0.370** | 24% | 0.42 | -0.379 | 41% | 13.0 |
| I1_partial_chand2_eod | 215 | 70 | +0.002 | **-0.372** | 31% | 0.35 | -0.486 | 29% | 12.1 |
| I2_chand2_eod | 215 | 70 | -0.051 | **-0.446** | 19% | 0.23 | -0.650 | 3% | 9.2 |
| I3_partial_chand3_eod | 215 | 70 | -0.017 | **-0.389** | 31% | 0.32 | -0.526 | 34% | 12.6 |
| I5_fixed1.5R_eod | 215 | 70 | +0.049 | **-0.352** | 26% | 0.43 | -0.379 | 36% | 11.9 |
| I6_partialTP_eod | 215 | 70 | +0.014 | **-0.324** | 31% | 0.43 | -0.380 | 34% | 11.8 |
| I4_partial_chand2_hold | 215 | 70 | -0.017 | **-0.394** | 39% | 0.41 | -0.422 | 0% | 15.5 |
| **S6_VWAP_reclaim** | | | | | | | | | |
| I0_fixed2R_eod | 1,634 | 623 | -0.078 | **-0.230** | 36% | 0.62 | -0.212 | 39% | 9.1 |
| I1_partial_chand2_eod | 1,634 | 623 | -0.120 | **-0.225** | 45% | 0.58 | -0.242 | 35% | 9.0 |
| I2_chand2_eod | 1,634 | 623 | -0.082 | **-0.214** | 34% | 0.61 | -0.201 | 33% | 8.9 |
| I3_partial_chand3_eod | 1,634 | 623 | -0.118 | **-0.226** | 45% | 0.58 | -0.243 | 40% | 9.2 |
| I5_fixed1.5R_eod | 1,634 | 623 | -0.081 | **-0.222** | 38% | 0.63 | -0.216 | 30% | 8.2 |
| I6_partialTP_eod | 1,634 | 623 | -0.117 | **-0.218** | 45% | 0.59 | -0.237 | 34% | 8.5 |
| I4_partial_chand2_hold | 1,634 | 623 | -0.124 | **-0.217** | 43% | 0.70 | -0.135 | 0% | 10.5 |
| **S3i_EMA_cross** | | | | | | | | | |
| I0_fixed2R_eod | 5,740 | 2,539 | -0.044 | **-0.332** | 32% | 0.45 | -0.353 | 45% | 10.0 |
| I1_partial_chand2_eod | 5,740 | 2,539 | -0.078 | **-0.304** | 39% | 0.45 | -0.363 | 39% | 9.5 |
| I2_chand2_eod | 5,740 | 2,539 | -0.042 | **-0.306** | 29% | 0.44 | -0.353 | 28% | 8.8 |
| I3_partial_chand3_eod | 5,740 | 2,539 | -0.074 | **-0.307** | 39% | 0.44 | -0.367 | 43% | 9.9 |
| I5_fixed1.5R_eod | 5,740 | 2,539 | -0.053 | **-0.302** | 34% | 0.49 | -0.325 | 39% | 9.3 |
| I6_partialTP_eod | 5,740 | 2,539 | -0.077 | **-0.297** | 39% | 0.46 | -0.351 | 40% | 9.4 |
| I4_partial_chand2_hold | 5,740 | 2,539 | -0.084 | **-0.194** | 41% | 0.73 | -0.115 | 0% | 11.3 |

## 4. What conditions outcome? (all triggers, baseline exit, all periods)

**S5_ORB**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 1,955 | -0.035 | 44% |
| time of entry | 10:30-11:15 | 1,224 | -0.079 | 41% |
| time of entry | 11:30-12:30 | 509 | -0.056 | 46% |
| gap at open | gap<-0.5ATR | 353 | -0.090 | 39% |
| gap at open | -0.5..-0.1 | 932 | +0.026 | 47% |
| gap at open | flat | 880 | -0.110 | 42% |
| gap at open | +0.1..+0.5 | 1,094 | -0.030 | 44% |
| gap at open | gap>+0.5ATR | 429 | -0.133 | 39% |
| cum ToD rvol | <0.8 | 1,341 | -0.066 | 44% |
| cum ToD rvol | 0.8-1.2 | 1,473 | -0.062 | 42% |
| cum ToD rvol | 1.2-1.8 | 649 | -0.010 | 46% |
| cum ToD rvol | 1.8-3 | 188 | +0.039 | 45% |
| cum ToD rvol | >3 | 37 | -0.421 | 19% |
| session RS | RS>0 vs SPY | 3,233 | -0.050 | 43% |
| session RS | RS≤0 | 455 | -0.069 | 45% |
| daily trend | 50>200 & above | 2,610 | -0.075 | 43% |
| daily trend | above 200 only | 254 | -0.091 | 43% |
| daily trend | below 200 | 824 | +0.031 | 46% |

**S6_VWAP_reclaim**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 1,348 | -0.140 | 37% |
| time of entry | 10:30-11:15 | 2,103 | -0.136 | 38% |
| time of entry | 11:30-12:30 | 1,736 | -0.207 | 37% |
| time of entry | 12:45-14:00 | 1,816 | -0.118 | 41% |
| time of entry | 14:15-15:45 | 1,169 | -0.174 | 41% |
| gap at open | gap<-0.5ATR | 701 | -0.090 | 40% |
| gap at open | -0.5..-0.1 | 2,189 | -0.121 | 40% |
| gap at open | flat | 1,999 | -0.180 | 38% |
| gap at open | +0.1..+0.5 | 2,378 | -0.190 | 38% |
| gap at open | gap>+0.5ATR | 905 | -0.123 | 39% |
| cum ToD rvol | <0.8 | 3,299 | -0.195 | 37% |
| cum ToD rvol | 0.8-1.2 | 3,120 | -0.144 | 39% |
| cum ToD rvol | 1.2-1.8 | 1,356 | -0.094 | 41% |
| cum ToD rvol | 1.8-3 | 338 | -0.114 | 39% |
| cum ToD rvol | >3 | 59 | +0.068 | 41% |
| session RS | RS>0 vs SPY | 3,439 | -0.149 | 39% |
| session RS | RS≤0 | 4,733 | -0.157 | 39% |
| daily trend | 50>200 & above | 5,709 | -0.151 | 39% |
| daily trend | above 200 only | 489 | -0.122 | 42% |
| daily trend | below 200 | 1,974 | -0.169 | 37% |

**S3i_EMA_cross**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 2,237 | -0.098 | 40% |
| time of entry | 10:30-11:15 | 2,522 | -0.115 | 40% |
| time of entry | 11:30-12:30 | 2,165 | -0.151 | 41% |
| time of entry | 12:45-14:00 | 2,158 | -0.144 | 41% |
| time of entry | 14:15-15:45 | 1,785 | -0.138 | 41% |
| gap at open | gap<-0.5ATR | 756 | -0.207 | 39% |
| gap at open | -0.5..-0.1 | 3,149 | -0.121 | 40% |
| gap at open | flat | 2,793 | -0.115 | 42% |
| gap at open | +0.1..+0.5 | 3,261 | -0.117 | 40% |
| gap at open | gap>+0.5ATR | 908 | -0.167 | 38% |
| cum ToD rvol | <0.8 | 4,666 | -0.160 | 40% |
| cum ToD rvol | 0.8-1.2 | 4,230 | -0.097 | 41% |
| cum ToD rvol | 1.2-1.8 | 1,553 | -0.113 | 41% |
| cum ToD rvol | 1.8-3 | 365 | -0.123 | 40% |
| cum ToD rvol | >3 | 53 | -0.277 | 32% |
| session RS | RS>0 vs SPY | 7,733 | -0.125 | 40% |
| session RS | RS≤0 | 3,134 | -0.137 | 41% |
| daily trend | 50>200 & above | 7,624 | -0.130 | 40% |
| daily trend | above 200 only | 655 | -0.159 | 39% |
| daily trend | below 200 | 2,588 | -0.114 | 42% |
