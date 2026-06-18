# Intraday Re-Test on Real EURUSD M1 — and the 2-Week Verdict

## Data used (real, verified)
- User-supplied **EURUSD 1-minute** export from MetaTrader 5.
- **1,860,324 bars, 2021-01-04 → 2025-12-31**, ~372k bars/year, clean Mon–Fri.
- Real OHLC **plus a real per-bar spread column** (median **1.1 pips** in liquid
  hours, ~3.5 pips at the 00:00 rollover, spikes to 25 pips on news).
- (The first upload was mislabeled: filename said 2021–2026 but contained only
  3 holiday days, Dec 29–31 2025, with 7–18 pip spreads. Rejected. The M1 zip is good.)

## What the intraday re-test showed
Every standard intraday strategy is **net negative after the real spread**:

| Strategy (15m/30m, many params) | Best expectancy after cost |
|---|---|
| EMA cross momentum | −0.07R |
| N-bar breakout | −0.075R |
| Bollinger mean-revert | −0.054R |
| RSI mean-revert | −0.052R |
| London/NY opening-range breakout | −0.036R |

Hour-of-day forward returns are all **< 0.3 pip** in liquid hours (round-trip cost
is ~1.3 pip). The only "big" hours (00:00 +2.0p, 23:00 −1.3p) are the illiquid
rollover where spreads are widest — not tradeable. **EURUSD intraday is efficient;
no simple, robust directional edge survives realistic cost.**

This is the opposite of the daily-close backtest (+0.245R). That edge was real but
tiny, and only looks good because a daily move dwarfs the spread — intraday, the
spread dwarfs the edge.

## The 2-week goal — quantified verdict: NOT achievable legitimately
FTMO simulator with a hard **10-trading-day deadline**, intraday daily-loss enforced
on real max-adverse-excursion:

Best intraday strategy, pass within 2 weeks:
| Risk/trade | PASS | Blow-up | Missed deadline |
|---|---|---|---|
| 1% | 1.1% | 8% | 91% |
| 2% | 7.5% | 26% | 67% |
| 3% | 11.1% | 29% | 60% |
| 5% | 16.8% | 42% | 41% |

Peak ~17% pass — and only by gambling at 5% risk with 42% blow-ups. Never near 80%,
because there is no edge to compound; a sprint is pure variance.

The legitimate **daily** strategy, pass *within a deadline*:
| Deadline | best PASS (any risk ≤2%) |
|---|---|
| 2 weeks | **0%** (too few trades to reach +10%) |
| 4 weeks | ~5% |
| 8 weeks | ~20% |
| 24 weeks | ~56% |
| 52 weeks | ~79% |

## Bottom line
- A **≥80% pass within 2 weeks is impossible with a legitimate, data-backed edge**
  on EURUSD. Intraday has no edge after cost; the daily edge can't make +10% in 10 days
  without suicidal risk.
- The only honest lever to go *faster* without inflating risk is **more instruments**
  (trade several uncorrelated daily edges in parallel → more trades/week → reach target
  sooner). Even then, think ~2–3 months for ~80%, not 2 weeks.
- Refused to curve-fit a fake intraday strategy to hit the 2-week number — that would
  be the time-wasting, non-legitimate result you said to avoid.
