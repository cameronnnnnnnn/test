# v4 — FINAL deployable strategy (FTMO $15k 1-Step, NAS100)

The best honest monthly-pass config found across the entire v2/v3 search, on the
**bug-fixed** engine (partial-accounting fix + conservative intra-bar trailing).

## The strategy
| | |
|---|---|
| **Setup A** | US Opening-Range Breakout — 16:00 server, first 15-min range, 50pt stop, volume-confirmed, **hard 4R take-profit** (no trail/BE/scale-out) |
| **Setup B** | VWAP trend-pullback — 40pt stop, **hard 4R take-profit** |
| Both | one trade/day each, US cash session, flat 22:55 server, **Fridays on**, EOD-flat |
| Risk | **1.0% / trade** (≤2 trades/day → ≤2% daily, under the 3% cap) |
| Cost modeled | 2pt round-turn (US100.cash spread; FTMO indices commission-free) |

## Verified result (`strategy_v4.py`)
| deadline | pass | blow | median days-to-pass |
|---|---|---|---|
| 2 weeks | 27% | 27% | 7 |
| 3 weeks | 36% | 38% | 8 |
| **4 weeks** | **41%** | 44% | **8** |
| 8 weeks | 47% | 51% | 9 |

trades ~9.9/wk · WR 28% · expR +0.069R · PF 1.09

**Median time-to-pass is 8 days (well under 4 weeks).** The 4-week pass rate is ~41%
— **>50%/4wk is not attainable on NAS100 under FTMO's 3% daily cap** (proven from the
daily-Sharpe, swing, ensemble, gold, and barrier-math angles — see `../v3/RESULTS3.md`).

## Why this is still worth running (the convex payoff)
Losses are capped at the ~$89 challenge fee; wins are realized. Even at ~40% pass the
net EV is strongly positive (~+$400–550 per attempt). Run at low risk over repeated,
fee-refundable attempts.

## Files
- `strategy_v4.py` — the strategy + verification (prints the table above)
- `NAS100_v4.mq5` — MT5 EA. Inputs: `TakeProfitR=4`, `RiskPercent=1.0`, `UseA_ORB=true`,
  `UseB_Pullback=true`, `UseC_Fade=false`, `UseScaleOut=false`, `NoFridayEntry=false`.
  Hedging account, US100/NAS100 chart, M1, server time EET/EEST.
- `engine.py`/`ftmo.py`/`strategies.py`/`data.py`/`run.py` — bug-fixed core (copied).

## Honest caveats
- Edge is thin (+0.069R) and NAS-bull-skewed; ~44% blow-up at r=1% — size as risk
  capital and lean on the convex payoff over many attempts, not one.
- `>50%/4wk would require a ~55%-WR 1:1 edge` (NAS caps ~53.5%) or a 5%-daily product.
- Reproduce: `python3 strategy_v4.py`.
