# FTMO $15k 1-Step — the 88% / ~2-month config (aggressive)

Same strategy as `FTMO_95_Strategy`, **only the risk is raised (1.0% → 1.25%)** to pass faster.
You're buying ~1.2 months of speed with ~7pp of pass rate and ~2.6× the ruin risk.

## What changed vs the 95% config
**Nothing except `RiskPercent = 1.25`** (was 1.0). Entry, vol gate, partial, trail, sessions — all identical.

## Verified numbers (10k-run block-bootstrap MC, full FTMO rules, real static $13,500 floor)
| metric | 88% config (1.25% risk) | 95% config (1.0% risk) |
|---|---|---|
| **Pass — static floor (real FTMO)** | **88.3%** | 95.9% |
| **Blow-up — static floor** | **11.6%** | 4.4% |
| Median time to pass | **~2.3 months** | ~3.5 months |
| Pass — trailing floor (stress) | 69.3% | 77% |
| Per-trade edge (OOS 90% CI) | +0.001 … +0.361 | same (same trades) |

## The honest tradeoff — read this
- **1-in-9 chance you blow the account** (11.6%) vs 1-in-23 (4.4%) at 1.0% risk. The strategy's worst
  historical drawdown was ~12.8% of account at 1.0% risk → **~16% at 1.25% risk**, well past FTMO's
  10% max-loss. That excess is exactly where the extra blow-ups come from.
- It's the *same edge* — you're not getting more skill, just betting bigger to finish sooner.
- If a blown $15k challenge costs you the fee + reset, weigh the ~1.2 months saved against a 2.6×
  higher chance of paying again.

## Reproduce
```bash
python3 FTMO_88_Strategy/verify.py
```

## Deploy
`NAS100_ORB_88.mq5` — standalone EA, **MagicBase 7900000** (coexists with the sprint EA at 7700000
and the 95% EA at 7800000). Set `RiskPercent = 1.25`, `TakeProfitR = 0`. Compile in MetaEditor and
backtest in the Strategy Tester before live use. Hedging account required.
