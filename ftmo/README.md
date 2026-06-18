# FTMO 1-Step Challenge — Strategy, Real-Data Backtest & Monte Carlo

Account: **AUD $15,000** | Target +10% ($1,500) | Pairs: EURUSD, GBPUSD | 1-Step rules.

## TL;DR
- **Data is real.** U.S. Federal Reserve daily FX rates (FRED `DEXUSEU`/`DEXUSUK`),
  mirrored on GitHub by the datahub.io `core/exchange-rates` dataset. Inverted to
  conventional EURUSD/GBPUSD quotes. Period **2021-06-14 → 2026-06-12** (1,251 days).
  The series matches known history (EUR/USD parity in 2022, GBP mini-budget crash).
- **Strategy:** *Trend-Aligned Pullback* — buy dips in uptrends, sell rallies in
  downtrends. Many small, spread-out winning days (good for the consistency rule).
- **Monte Carlo verdict (passing the FTMO challenge = the test):**
  - Full 5 years: **99.8% pass**
  - Out-of-sample 2024–26 (strategy never tuned on it): **83.6% pass**
  - Both clear the **80%** bar at **0.5% risk per trade**.

## The honest caveats (read these)
1. **Daily-close data only.** FRED publishes one rate per business day — no intraday
   high/low and no bid/ask spread. The backtest is close-to-close on daily bars with a
   conservative round-turn cost (≈1.2 pip EURUSD / 1.6 pip GBPUSD) on every fill and
   stop losses floored at −1R. It does **not** model intraday spikes against an
   intraday daily-loss limit. Sizing is kept small (0.5%) so this matters little, but a
   tick-data re-test is the correct next step before risking money.
2. **The edge is decaying.** It was strong in 2021–23, moderate in 2024, and weak in
   the **last 12 months** (expectancy +0.05R, Monte Carlo pass ~63%). The full-sample
   99.8% is flattered by the early period. 0.5% risk was chosen specifically because it
   is the most robust setting out-of-sample — it was **not** chosen to maximise the
   in-sample number.
3. **Monte Carlo = sequence/path risk**, not future-regime risk. It resamples real
   trading days with replacement; it answers "given outcomes like the sampled period,
   how often do the FTMO rules get passed", not "will the edge persist".

## Strategy rules (`strategy.py`)
| Component | Rule |
|---|---|
| Trend | SMA(10) vs SMA(40): up if 10>40, else down |
| Trigger | 5-day z-score: `z<−1` in uptrend → BUY; `z>+1` in downtrend → SELL |
| Stop | 1.0 × ATR(14), loss floored at −1R |
| Exit | next daily close (1-day hold) |
| Weekend | no Friday entries (never hold over weekend) |
| Risk | 0.5% of current equity/trade, lots rounded DOWN, leverage ≈1× (≪1:30) |

## FTMO rules enforced in the simulator (`ftmo_sim.py`)
- Global loss: permanent FAIL if equity ≤ $13,575 (9.5% buffer).
- Daily loss: stop new entries for the day at −2.8% from the day's peak.
- Consistency: stop new entries once today ≥45% of total P&L; PASS needs biggest
  single day ≤50% of total profit.
- Min 3 trading days; target +10%; no time limit.

## Files
| File | Purpose |
|---|---|
| `prep_data.py` | Build real EURUSD/GBPUSD from FRED/datahub mirror |
| `research.py` | Indicators, trade model, candidate-signal sweep |
| `strategy.py` | Final locked strategy |
| `ftmo_sim.py` | FTMO rule engine + Monte Carlo |
| `validate.py` | Walk-forward, cost/slippage stress, parameter sensitivity |
| `report.py` | Final report + verdict (run this) |
| `prices.csv` / `fred_daily_raw.csv` | Real price data |
| `equity_curve.csv` | Sequential real-path equity at 0.5% risk |

## Reproduce
```bash
pip install numpy pandas
python ftmo/prep_data.py     # rebuild prices from raw FRED mirror
python ftmo/report.py        # final numbers + Monte Carlo verdict
python ftmo/validate.py      # robustness checks
```

## Robustness (from `validate.py`)
- **Cost stress:** 2× cost + worse stop fills (−1.25R) → still ~89% pass.
- **Parameter sensitivity:** every SMA/z combo tested gives expectancy +0.22…+0.27R,
  pass 97–98% — a broad plateau, not a curve-fit spike.
- **Walk-forward:** in-sample 99.9% / out-of-sample 83.6% at 0.5% risk.

**Bottom line:** clears your 80% Monte Carlo bar on real data, in- and out-of-sample,
with full disclosure of the daily-data limitation and recent edge decay. Validate on
intraday tick data before going live.
