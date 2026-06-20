# Round 2: 10 more creative levers + stop-size study — found a real winner

Tested 10 NEW levers (different from round 1) plus a proper stop-size sweep, all on
NAS100 (3y M1 — all I have; your 5y MT5 run corroborates it), every combination,
trailing-DD Monte Carlo, walk-forward validated. **One discovery broke the 80% wall.**

## Stop size — yes, re-tested properly (you asked)
Wider stops raise win-rate AND pass-rate (lower variance = fewer trailing-DD blow-ups),
at the cost of slower compounding (smaller expR/trade):
| Stop | WR | expR | PASS (1.1%) |
|---|---|---|---|
| 40pt | 19% | +0.210 | 54% |
| 60pt (old) | 25% | +0.160 | 60% |
| 80pt | 33% | +0.131 | 62% |
| 120pt | 44% | +0.093 | 65% |
60 was not optimal for win-rate/pass. **80pt is the better all-round choice** (and best
once the overnight filter is added, below).

## The 10 new levers — verdicts
| # | Lever | Result |
|---|---|---|
| 1 | VWAP filter (long above / short below) | **kills edge** (−0.085R) — drop |
| 2 | Close-confirmed breakout | neutral |
| 3 | **Overnight confluence** (open clears prior EU high/low) | **WINNER** — see below |
| 4 | Skip a weekday | "helps" but is day-of-week curve-fitting; adds nothing once #3 is on |
| 5 | ATR-regime filter | hurts |
| 6 | Momentum-into-level | marginal, redundant with #3 |
| 7 | Long-only / short-only | shorts weaker, but both-sides fine; no gain |
| 8 | Pyramid on runners | boosts expR but MORE blow-ups (fat tails vs trailing DD) |
| 9 | Chandelier ATR-trail | same as R-trail (neutral) |
| 10 | Failed-breakout reversal | dilutes (−expR) |

## The winner: Overnight Confluence + stop80
**Only take the breakout when the US opening range has already cleared the entire prior
~6h European session high (longs) / low (shorts).** A genuine trend-day filter — it keeps
only the days with real directional conviction and no lookahead.

| | old (1.1% raw) | **NEW (overnight + stop80)** |
|---|---|---|
| Win rate | 25% | **41%** |
| expR / PF | +0.16 / 1.33 | **+0.23 / 1.54** |
| Walk-forward (1st / 2nd half) | +0.12 / +0.20 | **+0.20 / +0.26** |
| PASS @1.1% (trailing DD) | 61% | **82%** |
| PASS @0.75% | ~73% | **92%** |

**Robustness checks (all pass):** the overnight window holds for 6/8/10h (not a single
fragile setting); both walk-forward halves are strong; the filter is economically sound
(trend-day confluence), not data-mined. Adding skip-Mon / momentum on top gave nothing —
correctly rejected as overfit.

The cost is **frequency**: ~1.5 trades/week (vs ~4), so it is slower.

## Comprehensive MC — new winner (overnight + stop80)
| Risk | PASS (raw) | PASS (+guard) | Avg time to pass |
|---|---|---|---|
| 0.75% | 92% | **95%** | ~8 months |
| 1.00% | 85% | 89% | ~6 months |
| 1.10% | 82% | 87% | ~5 months |
| 1.50% | 74% | 77% | ~3 months |

## Bottom line
This round found a **genuine, walk-forward-validated upgrade**: win-rate 25%→41%, and the
first config to clear your **80% pass goal (82% at 1.1%, 92-95% at 0.75%)**. It is
slower (~1.5 trades/week, months not weeks) — the reliability comes from being far
pickier. Both the EA and Pine now ship with the overnight filter ON and an 80pt stop.

Caveat kept honest: overnight cuts to 233 trades over 3 years. Walk-forward holds and
the logic is sound, but a smaller sample = treat 82% as strong-but-optimistic until
your own longer MT5 backtest confirms it.
