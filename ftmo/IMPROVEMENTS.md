# 10 Improvements — implemented, every combination searched, honestly judged

Took the validated NAS100 ORB (config B) and built 10 creative improvement levers,
each toggleable, then ran combinations through the full FTMO-rule Monte Carlo.
Two survived honest scrutiny; the rest were neutral or harmful (and two had bugs
that faked spectacular results until caught and fixed).

## The 10 ideas and verdicts
| # | Idea | Result | Verdict |
|---|---|---|---|
| 1 | **Range filter** (skip range <0.5x or >2x its 40d median) | expR +0.129→+0.165, 8wk pass 44→49%, blow ↓ | **KEEP** |
| 2 | Early-break window (only breaks within 60m of range) | neutral | drop |
| 3 | Retest entry (enter on pullback to level) | expR turns **negative** (−0.025) | drop |
| 4 | ATR-adaptive stop (k×ATR vs fixed 60) | much worse (too tight, kills tails) | drop |
| 5 | Range-width stop | more blow-ups | drop |
| 6 | Partial scale-out @ +2R | worse (caps the fat tails that drive passes) | drop |
| 7 | Re-entry after a fakeout stop | adds low-quality trades, expR ↓ to +0.078 | drop |
| 8 | **Volume confirmation** (breakout bar vol > range avg) | expR +0.165→+0.169, small pass ↑, blow ↓ | **KEEP** |
| 9 | Overnight-gap momentum filter | worse | drop |
| 10 | Anti-streak risk scaling [MC] | blow-up →~3% but pass −12% | optional (ultra-safe only) |

### Two bugs I caught (honesty note)
- "Partial @2R" first showed **win 100% / expR +1.065** — impossible. I was crediting
  the +2R partial even on days it never reached +2R. Fixed → it's just worse than baseline.
- "Re-entry" first showed **8wk 92% pass** — I was overwriting the first trade's loss
  with the winning re-entry (deleting real losses). Fixed → re-entry is worse than baseline.
  Reporting the fixed numbers, not the fantasy ones.

## Winning combination: Range filter + Volume confirmation
| Metric | config B | **improved** |
|---|---|---|
| expR | +0.129 | **+0.169** |
| Walk-forward in-sample / out-of-sample | +0.131 / +0.124 | **+0.152 / +0.194** |
| 8-week pass @ r=1% | ~44% | **~49%** |
| 8-week blow-up @ r=1% | ~14% | **~12%** |
| 24-week pass ceiling @ r=1% | ~69% | **~76%** |

The improvement **holds out-of-sample** (OOS expR is actually higher than in-sample),
so it is a real structural gain, not curve-fit. Both levers are principled: trade only
when the opening range is "normal" sized AND the breakout has real volume behind it.

## Improved strategy — full FTMO deadline × risk (all 5 rules)
Pass% / Blow-up%:
| Deadline | r=1.0% | r=1.25% | r=1.5% | r=2.0% |
|---|---|---|---|---|
| 2 weeks | 8 / 0 | 12 / 1 | 16 / 5 | 21 / 15 |
| 3 weeks | 18 / 2 | 24 / 6 | 29 / 11 | 36 / 23 |
| 4 weeks | 26 / 4 | 34 / 9 | 40 / 15 | 46 / 28 |
| 6 weeks | 40 / 8 | 48 / 15 | 53 / 22 | 56 / 34 |
| 8 weeks | 49 / 12 | 57 / 19 | 59 / 27 | 59 / 36 |
| 12 weeks | 62 / 15 | 66 / 24 | 65 / 30 | 61 / 38 |
| 24 weeks | 76 / 20 | 72 / 27 | 68 / 32 | 62 / 38 |

## Verdict
- The improvements are **real and validated** — ~5-7 points of extra pass rate and a
  higher ceiling (~76% at 24 weeks vs ~69%). Best free wins: range filter + volume.
- **The 2-3 week, 80% target is still not reachable** (3-week best ~36% at high risk).
  The ceiling rose but the edge-vs-10%-drawdown math still caps it below 80%.
- Recommended live config: **range filter ON, volume confirm ON, r = 1.0-1.25%, 8-12
  week horizon → ~50-66% pass.** The EA (NAS100_ORB.mq5) ships with both filters on.
