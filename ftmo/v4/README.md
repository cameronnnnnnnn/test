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

## Funded phase (`funded_phase.py`)
Different objective: steady monthly profit, not racing +10%. Same 3% daily / 10%
overall limits, no profit target. Best config = the 4R combo (only positive-EV one)
+ a **monthly profit-lock** (stop trading the month once +3% is banked → lock it green).

| risk | P(month ≥3%) | blow | mean/mo | use |
|---|---|---|---|---|
| 0.25% | 42% | **0%** | +0.5% | max preservation |
| **0.35%** | **53%** | **1.8%** | +0.5% | **recommended (keep the account)** |
| 0.50% | 63% | 11% | +0.6% | more 3%-months, real blow risk |
| 0.75% | 68% | 24% | +0.6% | aggressive (likely to lose the account) |

**Your target of ≥90% of months ≥3% is NOT achievable on NAS100.** It needs monthly
Sharpe ~3 (daily ~0.7); NAS has ~0.05. The mean monthly return caps ~+1–2%, *below* the
3% target, and high-WR/low-RR configs are net-negative after spread. Honest best is
~53% of months ≥3% at a preservation-safe risk. Your 2.45% break-even is reached in
~2–3 months, then net profit — the plan works, just not at 90%/3% consistency.

### Withdrawal-maximization (`withdraw_phase.py`) — re: the prop-firm heatmap
The video's heatmap (0.5R + dd_frac sizing) is **TOPSTEP** (zero-EV toys, trailing DD,
NO 3% daily cap). On NAS/FTMO it **inverts**: NAS's tight-TP (0.5R) is *negative*-EV
after spread, and `dd_frac` sizing breaches the 3% daily cap. So the **opposite** wins —
the positive-EV **4R combo at LOW fixed risk** maximizes money extracted. The *framing*
(optimize withdrawals via the convex payoff, low risk) is right; the geometry isn't.

**The right metric is TOTAL LIFETIME extraction per funded account** (the video's
$8,900/$50k = 17.8% is a lifetime average, not monthly). NAS/FTMO 4R combo, run to
account death:

| risk | buffer | avg lifetime payout | median | avg life |
|---|---|---|---|---|
| 0.40% | 0% | **17.7%** | 10.3% | 6.6 mo |
| 0.40% | 10% | **29.4%** | 7.7% | 16 mo |
| 0.40% | 15% | **34.1%** | 4.6% | 20 mo |

So NAS/FTMO **matches or beats** the video's 17.8%. **Your plan EV** (FTMO $15k, 90/10
split, ~2.45 challenges @ $135 to fund ≈ $331): avg payout/funded ≈ **$4,600** (you keep
90%) → **net ≈ +$4,300 per funded account**. Break-even is ~2.45% extraction; you average
~17–34% → **strongly net +EV**.

**Caveat — the average is right-skewed.** Median account extracts ~5–10% (a few long-lived
accounts pull the average up). Both still beat break-even. **Recommended:** r=0.4–0.5%,
buffer 5–10% (balances avg vs median vs lifespan). Higher buffer = higher *average* via
longer survival, lower median.

## Honest caveats
- Edge is thin (+0.069R) and NAS-bull-skewed; ~44% blow-up at r=1% — size as risk
  capital and lean on the convex payoff over many attempts, not one.
- `>50%/4wk would require a ~55%-WR 1:1 edge` (NAS caps ~53.5%) or a 5%-daily product.
- Reproduce: `python3 strategy_v4.py`.
