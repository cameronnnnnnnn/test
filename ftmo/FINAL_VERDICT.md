# Final Verdict — Can a legit strategy pass FTMO in 2–3 weeks at ≥80% under a 3% daily cap?

## Answer: No. Not with a legitimate, data-backed edge. Here is the proof.

### Data tested (all real, user-supplied MT5 M1, 2021–2025, ~1.86M bars each)
EURUSD, GBPUSD, AUDUSD, USDJPY — real OHLC + real per-bar spread (1.1–1.4 pip liquid).

### Every edge we could test, after real spread:
| Approach | Result |
|---|---|
| Intraday momentum / EMA cross (4 pairs, sessions) | −0.10 to −0.14R (lose) |
| Intraday breakout (4 pairs, sessions) | −0.08 to −0.12R (lose) |
| Intraday mean-revert BB / RSI (4 pairs, sessions) | −0.05 to −0.16R (lose) |
| Opening-range breakout (London & NY) | −0.04 to −0.13R (lose) |
| Hour-of-day directional drift | all < cost (no edge) |
| **Daily trend-aligned pullback (EUR/GBP)** | **+0.10R (small real edge)** |
| Daily pullback (AUD/JPY) | ~0 / negative |
| Statistical arbitrage EUR–GBP spread (daily & intraday) | −0.01 (lose after 2-leg cost) |

The only positive edge is the **daily** EUR/GBP pullback, ~+0.10R, ~2 trades/week.

### Deadline Monte Carlo on the legit multi-pair daily strategy (3% daily cap enforced):
| Deadline | Best PASS (r≤1%) |
|---|---|
| 2 weeks | ~0.3% |
| 3 weeks | ~1.6% |
| 8 weeks | ~14% |
| 16 weeks | ~33% |
| unlimited | ~64% (ceiling) |

In 2–3 weeks it is essentially 0%. Even with unlimited time the real edge tops out
around 64% — it never reaches 80%, because the edge is thin and intraday stops
(now modeled with real highs/lows) cut the winners the close-only FRED data had let run.

### Why it is mathematically impossible (not a matter of trying harder)
To make +10% in T trading days without ever losing >3% in a day:
- Required average gain: (1.10)^(1/T) − 1 → **0.96%/day** (2 wks) or **0.64%/day** (3 wks).
- Expected daily gain = (risk deployed per day) × (edge per unit risk).
- The 3% daily cap limits prudently-deployed daily risk to ≈2%.
- Real edge per unit risk on liquid majors ≈ **0.05–0.10R** (and negative intraday).
- So max realistic expected daily gain ≈ 2% × 0.10 = **0.20%/day** — 3–5× short of target.
- Closing that gap means risking near the daily cap every day → it becomes a coin-flip
  sprint: ~15–20% pass, ~40% blow-up. **Speed (high variance) and 80% reliability
  (low variance) are mutually exclusive with a thin edge.**

### What is actually true
- **2–3 week, 80%, ≤3% daily, legit: impossible.** The numbers above are the proof.
- The best *legitimate* strategy (daily EUR/GBP pullback) is a slow grinder: ~60–64%
  per attempt and needs **months**, not weeks.
- A 2-week attempt is a ~15% gamble dominated by blow-ups — it fails your own 80% rule.

We refused to curve-fit a fake intraday strategy to hit the number. That would be the
illegitimate, time-wasting result you explicitly said to avoid.
