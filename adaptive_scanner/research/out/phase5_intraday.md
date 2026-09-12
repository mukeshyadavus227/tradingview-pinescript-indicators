# Phase 5 — INTRADAY_15M validation

48 symbols, 15m RTH bars 2025-12-08 → 2026-09-11; train < 2026-06-15 ≤ test. R net of 5 bps round trip unless stated. Trigger events: 22,830. **One regime only** — this can kill a strategy, not bless one.

## 1. Trigger vs eligible vs deployed, baseline exit (fixed 2R, EOD flat)

| population | n | mean R | hit | PF | SR/trade |
|---|---:|---:|---:|---:|---:|
| S5_ORB · all triggers · train | 2,500 | +0.012 | 46% | 1.03 | +0.012 |
| S5_ORB · eligible · train | 247 | +0.065 | 47% | 1.15 | +0.061 |
| S5_ORB · deployed · train | 247 | +0.065 | 47% | 1.15 | +0.061 |
| S5_ORB · all triggers · test | 1,189 | -0.189 | 38% | 0.64 | -0.192 |
| S5_ORB · eligible · test | 70 | -0.370 | 24% | 0.42 | -0.379 |
| S5_ORB · deployed · test | 70 | -0.370 | 24% | 0.42 | -0.379 |
| S6_VWAP_reclaim · all triggers · train | 5,467 | -0.124 | 40% | 0.78 | -0.108 |
| S6_VWAP_reclaim · eligible · train | 1,644 | -0.079 | 41% | 0.86 | -0.068 |
| S6_VWAP_reclaim · deployed · train | 1,640 | -0.078 | 41% | 0.86 | -0.068 |
| S6_VWAP_reclaim · all triggers · test | 2,708 | -0.212 | 36% | 0.65 | -0.194 |
| S6_VWAP_reclaim · eligible · test | 623 | -0.230 | 36% | 0.62 | -0.212 |
| S6_VWAP_reclaim · deployed · test | 622 | -0.228 | 36% | 0.63 | -0.211 |
| S3i_EMA_cross · all triggers · train | 7,533 | -0.058 | 44% | 0.88 | -0.055 |
| S3i_EMA_cross · eligible · train | 5,795 | -0.046 | 44% | 0.90 | -0.043 |
| S3i_EMA_cross · deployed · train | 5,644 | -0.047 | 44% | 0.90 | -0.044 |
| S3i_EMA_cross · all triggers · test | 3,433 | -0.282 | 34% | 0.52 | -0.287 |
| S3i_EMA_cross · eligible · test | 2,559 | -0.328 | 32% | 0.46 | -0.347 |
| S3i_EMA_cross · deployed · test | 2,520 | -0.326 | 32% | 0.46 | -0.344 |

## 2. Cost sensitivity (eligible, all periods, baseline exit)

| strategy | 0 bps | 2 bps | 5 bps | 10 bps |
|---|---:|---:|---:|---:|
| S5_ORB | +0.034 | +0.008 | -0.031 | -0.097 |
| S6_VWAP_reclaim | -0.009 | -0.054 | -0.120 | -0.231 |
| S3i_EMA_cross | -0.032 | -0.072 | -0.133 | -0.234 |

## 3. Exit models (eligible events)

| model | n train | n test | mean R train | mean R test | hit te | PF te | SR te | EOD% te | bars te |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **S5_ORB** | | | | | | | | | |
| I0_fixed2R_eod | 247 | 70 | +0.065 | **-0.370** | 24% | 0.42 | -0.379 | 41% | 13.0 |
| I1_partial_chand2_eod | 247 | 70 | +0.025 | **-0.372** | 31% | 0.35 | -0.486 | 29% | 12.1 |
| I2_chand2_eod | 247 | 70 | -0.024 | **-0.446** | 19% | 0.23 | -0.650 | 3% | 9.2 |
| I3_partial_chand3_eod | 247 | 70 | +0.011 | **-0.389** | 31% | 0.32 | -0.526 | 34% | 12.6 |
| I5_fixed1.5R_eod | 247 | 70 | +0.070 | **-0.352** | 26% | 0.43 | -0.379 | 36% | 11.9 |
| I6_partialTP_eod | 247 | 70 | +0.034 | **-0.324** | 31% | 0.43 | -0.380 | 34% | 11.8 |
| I4_partial_chand2_hold | 247 | 70 | +0.012 | **-0.394** | 39% | 0.41 | -0.422 | 0% | 15.5 |
| **S6_VWAP_reclaim** | | | | | | | | | |
| I0_fixed2R_eod | 1,644 | 623 | -0.079 | **-0.230** | 36% | 0.62 | -0.212 | 39% | 9.1 |
| I1_partial_chand2_eod | 1,644 | 623 | -0.122 | **-0.225** | 45% | 0.58 | -0.242 | 35% | 9.0 |
| I2_chand2_eod | 1,644 | 623 | -0.084 | **-0.214** | 34% | 0.61 | -0.201 | 33% | 8.9 |
| I3_partial_chand3_eod | 1,644 | 623 | -0.121 | **-0.226** | 45% | 0.58 | -0.243 | 40% | 9.2 |
| I5_fixed1.5R_eod | 1,644 | 623 | -0.083 | **-0.222** | 38% | 0.63 | -0.216 | 30% | 8.2 |
| I6_partialTP_eod | 1,644 | 623 | -0.120 | **-0.218** | 45% | 0.59 | -0.237 | 34% | 8.5 |
| I4_partial_chand2_hold | 1,644 | 623 | -0.127 | **-0.217** | 43% | 0.70 | -0.135 | 0% | 10.5 |
| **S3i_EMA_cross** | | | | | | | | | |
| I0_fixed2R_eod | 5,795 | 2,559 | -0.046 | **-0.328** | 32% | 0.46 | -0.347 | 45% | 10.0 |
| I1_partial_chand2_eod | 5,795 | 2,559 | -0.079 | **-0.302** | 39% | 0.45 | -0.361 | 39% | 9.5 |
| I2_chand2_eod | 5,795 | 2,559 | -0.043 | **-0.304** | 29% | 0.44 | -0.350 | 28% | 8.8 |
| I3_partial_chand3_eod | 5,795 | 2,559 | -0.075 | **-0.305** | 39% | 0.45 | -0.363 | 43% | 9.9 |
| I5_fixed1.5R_eod | 5,795 | 2,559 | -0.055 | **-0.299** | 34% | 0.50 | -0.320 | 39% | 9.3 |
| I6_partialTP_eod | 5,795 | 2,559 | -0.078 | **-0.295** | 39% | 0.46 | -0.348 | 40% | 9.4 |
| I4_partial_chand2_hold | 5,795 | 2,559 | -0.083 | **-0.193** | 41% | 0.73 | -0.114 | 0% | 11.3 |

## 4. What conditions outcome? (all triggers, baseline exit, all periods)

**S5_ORB**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 1,955 | -0.035 | 44% |
| time of entry | 10:30-11:15 | 1,224 | -0.079 | 41% |
| time of entry | 11:30-12:30 | 510 | -0.056 | 46% |
| gap at open | gap<-0.5ATR | 353 | -0.090 | 39% |
| gap at open | -0.5..-0.1 | 932 | +0.026 | 47% |
| gap at open | flat | 881 | -0.109 | 42% |
| gap at open | +0.1..+0.5 | 1,094 | -0.030 | 44% |
| gap at open | gap>+0.5ATR | 429 | -0.133 | 39% |
| cum ToD rvol | <0.8 | 1,310 | -0.070 | 44% |
| cum ToD rvol | 0.8-1.2 | 1,449 | -0.057 | 43% |
| cum ToD rvol | 1.2-1.8 | 679 | -0.026 | 45% |
| cum ToD rvol | 1.8-3 | 206 | +0.043 | 46% |
| cum ToD rvol | >3 | 45 | -0.228 | 29% |
| session RS | RS>0 vs SPY | 3,336 | -0.054 | 43% |
| session RS | RS≤0 | 353 | -0.041 | 45% |
| daily trend | 50>200 & above | 2,611 | -0.075 | 43% |
| daily trend | above 200 only | 254 | -0.091 | 43% |
| daily trend | below 200 | 824 | +0.031 | 46% |

**S6_VWAP_reclaim**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 1,348 | -0.140 | 37% |
| time of entry | 10:30-11:15 | 2,103 | -0.136 | 38% |
| time of entry | 11:30-12:30 | 1,738 | -0.208 | 37% |
| time of entry | 12:45-14:00 | 1,817 | -0.117 | 41% |
| time of entry | 14:15-15:45 | 1,169 | -0.174 | 41% |
| gap at open | gap<-0.5ATR | 701 | -0.090 | 40% |
| gap at open | -0.5..-0.1 | 2,189 | -0.121 | 40% |
| gap at open | flat | 2,001 | -0.181 | 38% |
| gap at open | +0.1..+0.5 | 2,379 | -0.189 | 38% |
| gap at open | gap>+0.5ATR | 905 | -0.123 | 39% |
| cum ToD rvol | <0.8 | 3,161 | -0.196 | 37% |
| cum ToD rvol | 0.8-1.2 | 3,079 | -0.139 | 39% |
| cum ToD rvol | 1.2-1.8 | 1,446 | -0.119 | 40% |
| cum ToD rvol | 1.8-3 | 403 | -0.115 | 39% |
| cum ToD rvol | >3 | 86 | +0.164 | 44% |
| session RS | RS>0 vs SPY | 3,558 | -0.159 | 39% |
| session RS | RS≤0 | 4,617 | -0.148 | 39% |
| daily trend | 50>200 & above | 5,712 | -0.150 | 39% |
| daily trend | above 200 only | 489 | -0.122 | 42% |
| daily trend | below 200 | 1,974 | -0.169 | 37% |

**S3i_EMA_cross**

| condition | bucket | n | mean R | hit |
|---|---|---:|---:|---:|
| time of entry | 09:30-10:15 | 2,323 | -0.103 | 39% |
| time of entry | 10:30-11:15 | 2,522 | -0.115 | 40% |
| time of entry | 11:30-12:30 | 2,174 | -0.149 | 41% |
| time of entry | 12:45-14:00 | 2,162 | -0.142 | 41% |
| time of entry | 14:15-15:45 | 1,785 | -0.138 | 41% |
| gap at open | gap<-0.5ATR | 770 | -0.208 | 39% |
| gap at open | -0.5..-0.1 | 3,171 | -0.119 | 40% |
| gap at open | flat | 2,826 | -0.114 | 42% |
| gap at open | +0.1..+0.5 | 3,278 | -0.117 | 40% |
| gap at open | gap>+0.5ATR | 921 | -0.176 | 37% |
| cum ToD rvol | <0.8 | 4,505 | -0.168 | 40% |
| cum ToD rvol | 0.8-1.2 | 4,239 | -0.104 | 41% |
| cum ToD rvol | 1.2-1.8 | 1,693 | -0.118 | 40% |
| cum ToD rvol | 1.8-3 | 449 | -0.030 | 45% |
| cum ToD rvol | >3 | 80 | +0.050 | 45% |
| session RS | RS>0 vs SPY | 7,908 | -0.133 | 40% |
| session RS | RS≤0 | 3,058 | -0.116 | 43% |
| daily trend | 50>200 & above | 7,693 | -0.130 | 40% |
| daily trend | above 200 only | 661 | -0.162 | 39% |
| daily trend | below 200 | 2,612 | -0.114 | 42% |
