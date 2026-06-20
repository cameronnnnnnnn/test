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

## Recommended 1-MONTH SPRINT preset
**Multi-session US ORB, no overnight filter (it kills frequency), stop 80, r=1.25%, guard OFF.**
- ~45% pass within 1 month, ~12% more pass in ~6 weeks, ~43% blow, WR ~31%.
- How to run it in MT5: **run TWO copies of the EA** on the NAS100 chart, identical
  except:
  - Copy A: `SessionOpenHour = 15`, `MagicNumber = 7700015`
  - Copy B: `SessionOpenHour = 16`, `MagicNumber = 7700016`
  - Both: `UseOvernightConf = false`, `StopDistance = 80`, `RiskPercent = 1.25`,
    `UseFloorGuard = false`, filters ON.
  - (Two instances = up to 2 trades/day = 2.5% worst-case daily, under the 3% cap.)

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
