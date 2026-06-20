# Passing within 1 month — the honest ceiling + best config

You want +10% inside 1 month (21 trading days). That is a **sprint**, and the math is
unavoidable: fast passing requires high variance, which means a high blow-up rate. Here
is the full Monte Carlo breakdown and the best config I could build for it.

## Why 1 month is hard
+10% in ~21 days needs ~0.5%/day. The edge delivers ~+0.16R/trade ≈ +0.18%/day at 1%
risk — about 3x too slow on drift alone. So a 1-month pass relies on catching a cluster
of fat-tail winners quickly. More shots (frequency) + more risk = more chance of that,
but also more blow-ups. There is no setting that is fast AND safe.

## The lever that helped: multi-session (more shots)
Stacking US opens (15h + 16h, and 14h) roughly doubles/triples trade frequency, which
lets you use LOWER risk to still reach +10% fast — keeping blow-ups flatter:
| Config | risk | **pass ≤1mo** | pass >1mo (avg) | blow | WR |
|---|---|---|---|---|---|
| 16h only | 2.0% | 37% | 8% | 56% | 25% |
| 15h+16h | 1.0% | 42% | 17% (32td) | 41% | 25% |
| **15h+16h stop80** | **1.25%** | **45%** | 12% | 43% | **31%** |
| 15h+16h stop60 | 1.25% | 46% | 8% | 47% | 25% |
| 14h+15h+16h | 1.0% | 47% | 7% | 47% | 21% |

**The ceiling for "pass within 1 month" is ~45-47%, with ~44-47% blow-up.** That is the
honest best. The floor guard lowers the 1-month pass (de-risking = slower), so for a
sprint you run it OFF.

## Recommended 1-MONTH SPRINT preset — definitive MC (r=1.25%)
**Multi-session US ORB (15h+16h), no overnight filter, stop 80, r=1.25%, guard OFF.**
Pooled edge: WR 31%, expR +0.125, PF 1.26, maxR 10.6.
| Outcome | r=1.0% | **r=1.25%** | r=1.5% |
|---|---|---|---|
| **PASS within 1 month** | 36% | **44%** | 47% |
| PASS after 1 month | 26% (~1.7mo) | 12% (~1.5mo) | 6% (~1.4mo) |
| **BLOW (10% trailing DD)** | 38% | **44%** | 47% |
| Total pass (any time) | 62% | 56% | 53% |
| Median time to pass | 18td | 13td | 10td |

## How to run it
**MT5 (easiest): `NAS100_ORB_sprint.mq5`** — one EA that trades BOTH the 15h and 16h
opens. Inputs are preset to the sprint (SessionHours="15,16", stop80, risk1.25, filters
ON, no overnight, no guard). **Requires a hedging account** (FTMO MT5 is hedging) since
two positions can be open at once. Check `SessionHours` matches your broker's server
hours for the US session, and backtest in the Strategy Tester first.

**Pine:** add `NAS100_ORB.pine` to the chart **twice**, set `useOvernight=false`,
`stopPts=80`, `riskPct=1.25`, and the two session opens (e.g. `0830-1600` and
`0930-1600` America/New_York). TradingView shows each instance's equity separately
(it cannot combine two concurrent strategies into one curve — use the MT5 sprint EA for
the true combined backtest).

## The choice you are actually making
| Goal | Config | Pass | Blow | Time |
|---|---|---|---|---|
| **Sprint (your ask)** | multi-session, r=1.25%, guard off | **~45%** | **~43%** | ≤1 month |
| Balanced | 16h, stop80, r=1.0%, guard on | ~64% | ~11% | ~2-3 months |
| Reliable | overnight+stop80, r=0.75%, guard on | **~92%** | ~5% | ~5-8 months |

A 1-month pass is roughly a coin flip with a ~43% chance of losing the account. That is
not a flaw in the strategy — it is what compressing a thin-edge target into 21 days costs.
If the account fee matters, the balanced or reliable presets are the smarter play; if you
just want the fastest shot and can stomach the blow-up odds, the sprint preset is above.
