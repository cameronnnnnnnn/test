# FTMO $15k pass-rate optimization — findings

**Goal:** maximize probability of passing the FTMO $15k 1-Step Challenge (NAS100), target ≥95%,
non-overfit. Loop: propose → backtest → MC → validate OOS → improve/restart.

## Answer: YES, a robust ≥95% is achievable — at the cost of time and by minimizing ruin, not by a strong edge.

### Winning config
- NAS100 ORB, **both sessions** (15:00 & 16:00 server), 30-min range, **80pt stop (1R)**, **BE@1R**,
  **3R hard TP**, range + volume filters, EOD-flat, **both directions (long + short)**.
- **NEW: causal volatility-regime filter** — only take a trade when the **prior day's** ATR
  percentile ≥ 0.5 (skip the ~50% lowest-volatility days, where breakouts are chop/fakeouts).
  Causal = uses the previous day's ATR, no lookahead.
- **Risk per trade: 0.50%** (down from the 1.25% run live). This is the single biggest lever.

### Result (10k Monte-Carlo, fresh $15k, FTMO rules incl. 50% best-day consistency)
| risk | floor | PASS | BLOW | median time |
|---|---|---|---|---|
| **0.50%** | static $13,500 (real FTMO) | **100.0%** | 0.0% | ~8 months |
| **0.50%** | trailing peak−10% (stress) | **99.9%** | 0.1% | ~8 months |
| 0.75% | static | 98.1% | 1.9% | ~4.3 months |
| 0.75% | trailing | 91.2% | 8.8% | ~4.3 months |

### Robustness evidence (why this isn't overfit)
- **Threshold plateau:** ATR-pct cutoffs 0.40 / 0.45 / 0.50 / 0.55 / 0.60 ALL give ~100% pass /
  ~100% worst-half. Broad plateau, not a tuned spike. (0.35 breaks → 81% worst-half.)
- **Causal, not lookahead:** prior-day regime matches the same-day version (regime is ~92%
  persistent), so the result is NOT lookahead-inflated.
- **Train/Test separation** (threshold fixed at 0.5): TRAIN (2022-10..2024-10) 100% pass, every
  half-year 100%; TEST (2024-10..2025-10) 100% pass, every half-year 100%.
- **Every sub-period passes** — the un-filtered baseline had a 2023H2 hole (79% worst-half, edge
  ≈ 0); the vol filter closes it.
- **Both floor models** hold at 0.50% risk.

### Honest caveats (read these)
1. **It's a low-ruin play, not a strong-edge play.** The per-trade edge point estimates are solidly
   positive (train +0.100, test +0.166) but the 90% bootstrap CIs graze zero on the filtered
   subsamples (smaller n). The ~100% pass comes from: tiny risk + shallow drawdowns (the filter
   removes the loss-heavy chop days) + modest positive drift + no time limit. If the true edge were
   genuinely ~zero, a low-risk run between symmetric ±10% barriers passes ~50%, not 100% — so the
   result is contingent on the positive drift being real (the data supports it; it isn't proven
   beyond doubt).
2. **≥95% costs ~6–8 months, not 3.** Clean time-vs-safety frontier: to get under 3 months you must
   raise risk to ~1.0%, which drops the robust pass rate below 95% (esp. under the trailing floor).
   You cannot have both robust-95% and sub-3-month.
3. **One instrument, one 3-year sample.** The plateau + train/test consistency are strong, but
   future regimes carry inherent risk. This is not a guarantee.
4. **~half the signals.** Skipping low-vol days ≈ 4 trades/week (vs ~7.5), which is why the calendar
   grind is long.

### The frontier (pick your point)
- **Max safety / pass:** 0.50% risk → ~100% pass, ~8 months.
- **Balanced:** ~0.65–0.70% risk → ~97–98% pass, ~5 months.
- **Fastest that still clears 95% (static floor only):** 0.75% risk → 98% pass, ~4.3 months.
- Sub-3-month is NOT compatible with robust ≥95%.

### To deploy
The MT5 EA does NOT yet implement the ATR-percentile vol filter (it lives only in the Python
backtest engine). Deploying this requires: (a) adding a causal daily-ATR-percentile gate to the EA,
(b) setting RiskPercent ≈ 0.50. Both are straightforward but not yet done.

Scripts: harness.py, walkforward.py, mc_honest.py, causal_volcheck.py, validate_final.py,
final_stress.py.
