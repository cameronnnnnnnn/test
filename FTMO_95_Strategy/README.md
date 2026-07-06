# FTMO $15k 1-Step — the 95% config

The chosen strategy: **~95.9% pass rate on FTMO's real (static $13,500) drawdown floor**, median
time to pass **~3 months**. Faster than the ultra-safe ~100%/5-month config, at the cost of ~4pp of
pass rate — the point on the frontier you picked.

## The strategy (plain English)
- **Market / entry:** NAS100 (US100.cash) opening-range breakout on the **15:00 and 16:00 server
  sessions**, 30-min range, **both long and short**. Stop = **80 points = 1R**.
- **Volatility gate:** only trade when the **prior day's** ATR percentile is **≥ 0.50** (skip the
  ~50% lowest-volatility days — the chop/fakeout days). Causal, no lookahead.
- **Exits (the mix):**
  - Breakeven stop at **+1R**.
  - **Scale out 50% at +2R**, move the remaining half to **breakeven**.
  - **Trail** the runner **5R** behind its extreme.
  - Flat by end of day — no overnight/weekend holds.
- **Risk:** **1.0% of balance per trade.**

## Verified numbers (10k-run block-bootstrap MC, full FTMO rules)
| metric | value |
|---|---|
| Pass — static floor (real FTMO) | **95.9%** |
| Blow-up — static floor | 4.4% |
| Pass — trailing floor (stress test) | 77.1% |
| Median time to pass | ~3 months |
| Per-trade edge (OOS test 90% CI) | +0.001 … +0.361 (clears zero) |

Rules modeled: +10% target ($16,500), static $13,500 max-loss floor, 3% daily loss, 50% best-day
consistency (dilutable), min 4 trading days, no time limit.

## Honest caveats
- This is a **low-ruin** result, not a bulletproof edge. The ~96% comes from modest risk + the vol
  filter's shallow drawdowns + no time limit carrying a small positive drift to target. The
  per-trade edge only just clears zero out-of-sample.
- The **95.9% assumes FTMO's real static floor.** A stricter *trailing* drawdown would drop this to
  ~77% at 1.0% risk — if you want robustness to that too, drop risk to ≤0.75% (→ ~100%, ~5 months).
- One instrument, one 3-year sample (2022–2025). Future regimes carry inherent risk.

## Reproduce
```bash
python3 FTMO_95_Strategy/verify.py
```

## Deployment gap (not yet built)
The live MT5 EA (`ftmo/mt5/NAS100_ORB_sprint.mq5`) does **not** yet implement:
1. the causal ATR-percentile volatility gate, or
2. the partial scale-out (50% at +2R → breakeven).
It also needs `RiskPercent` set to **1.0** and `TakeProfitR` set to **0** (trail the runner, no hard
TP). Building these into the EA is the remaining step to run this config live.

Full research trail: `ftmo/passopt/` (harness, sweep, verification, frontier) and
`ftmo/passopt/FINDINGS.md`.
