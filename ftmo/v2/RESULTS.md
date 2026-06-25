# NAS100 FTMO $15k — fresh strategy search (v2). Results & honest verdict.

**Goal set by the user:** a brand-new NAS100 strategy that passes the FTMO $15k
1-Step **>80% of the time in <3 weeks**. Only the *rules* were carried over from
prior work; every strategy, the backtest engine, and the validator were rebuilt
from scratch on real data.

**TL;DR:** Across mean-reversion, breakout, filtered, multi-session, combo, retest
and long-only families, the best legitimate 3-week pass rate is **~32%** (and that
only by gambling at 2%/trade with a 46% blow-up rate). **>80% in <3 weeks is not
reachable with a real edge** — and this is now *proven*, not asserted: it would
require a daily Sharpe of ~1.0, while the best strategy achieves ~0.056. The best
*deployable* strategy is documented below; run patiently it passes ~50–55% of
attempts over 8–12 weeks.

---

## Data, engine, validator (all rebuilt)
- **Data:** real FTMO MT5 **US100 M1**, 1,042,353 bars, **2022-10-18 → 2025-10-01**
  (~3y), 99.9% clean 1-min spacing. Timezone confirmed **EET/EEST (FTMO server)**
  from the tick-volume profile (US cash open lights up 16:00–17:00 server), so
  00:00 in the data = the FTMO daily reset. (`data.py`)
- **Contract/costs:** US100.cash = $1/index-point per 1.0 lot (USD); the account is
  AUD but the whole sim is **R-/%-based, so currency and point value cancel out**
  (a trade is sized so its stop = the chosen % of equity). Costs modeled as **2
  points round-turn** (spread+commission+slippage), stress-tested to 4 and 6.
- **Engine (`engine.py`):** fills on M1 bars, enters at next-bar open (no
  look-ahead), STOP-before-TP within a bar (conservative), and records each trade's
  **intraday MAE/MFE** so the FTMO limits can be checked on **floating** equity —
  the thing the prior daily-data work could not do.
- **Validator (`ftmo.py`):** bootstraps whole **trading days** into synthetic
  challenge attempts and enforces all five rules on floating equity: **+10% target,
  static $13,500 floor, 3% daily loss, min-4-days, and the 50% best-day consistency
  rule** (soft — it delays a pass, never fails it). Risk compounds off current
  balance like the live EA.

## The loop — every family tested (cost 2pt, best risk shown)

```
STRATEGY                          n t/wk    WR    expR    PF    r* | 3wk pass  blow | 4wk pass  blow
MeanRev: VWAP-fade k2.5         761  5.0 47.7% -0.080  0.85 2.50% |    12.1% 70.0% |    13.9% 76.8%
MeanRev: OR-fade tp1.5          720  4.7 40.1% -0.052  0.92 2.00% |    16.8% 43.4% |    20.7% 53.2%
Breakout: ORB hard-TP3+BE       762  5.0 20.1% -0.001  1.00 2.00% |    24.3% 39.2% |    29.0% 47.8%
Breakout: ORB trail2R           762  5.0 31.9% +0.057  1.10 2.00% |    27.6% 43.7% |    32.7% 50.9%
Breakout: London ORB            763  5.0 24.8% -0.074  0.90 2.00% |    18.0% 69.2% |    19.9% 74.7%
Breakout: ORB retest           755  4.9 30.2% +0.082  1.12 2.00% |    30.2% 48.2% |    34.8% 54.5%
Breakout: ORB long-only         705  4.6 31.9% +0.111  1.17 2.00% |    31.1% 45.4% |    36.0% 51.2%
** BEST: vol US ORB trail3      756  4.9 30.8% +0.110  1.16 2.00% |    32.5% 46.4% |    37.0% 52.2%
Combo: US16:00 + US16:30       1523 10.0 32.1% +0.078  1.12 1.00% |    28.6% 29.5% |    36.2% 36.8%
Combo: US16 + London10         1525 10.0 27.7% +0.007  1.01 1.00% |    23.4% 42.2% |    28.2% 50.5%
```

What the loop established:
1. **Mean-reversion loses.** Decent win rates (40–48%) but negative expectancy —
   NAS100 intraday *trends*; 1:1 fades can't clear costs. (Refutes the high-WR
   hypothesis I went in with, on the data.)
2. **Only US-open momentum has a real edge.** The London/EU open ORB is *negative*
   (−0.074R) — NAS has no EU-session edge. Breakout in the US cash open is the one
   durable positive (+0.11R).
3. **The edge lives in the uncapped fat right tail.** Trail 3R no-cap = +0.110R; a
   hard 3R take-profit collapses it to ~0.00R; trail 2R → ~0R. You *must* let
   winners run, which is exactly what raises daily variance and trips consistency.
4. **A volume filter is a small free gain** (+0.089 → +0.110R). Range/trend-day
   filters and the retest entry do not help.
5. **Combos cut blow-up but not pass.** US16:00+US16:30 halves blow-up (46%→30%)
   but pass stays ~29%, because the only positive edges are all correlated US-open
   momentum — there is **no second uncorrelated edge to stack**, so daily Sharpe
   barely moves.

## The best strategy (deployable)
**US opening-range breakout — `BEST` in `scoreboard.py`:**
- Instrument US100; **server 16:00**, build the **first 15-min** range (RH/RL).
- Enter at first break of RH (long) / RL (short); require the breakout bar's tick
  volume above the opening-range average.
- **50-point stop = 1R.** No hard take-profit, no breakeven. **Trail the stop 3R
  behind the running extreme.** Flat by 22:55 server. No Friday entries.
- One trade/day → max ~1R of daily risk (the 3% daily cap is never binding).

**Edge & robustness:**
- expR **+0.110**, WR 30.8%, PF 1.16, ~5 trades/wk, maxR ~10.
- **Out-of-sample holds:** in-sample +0.090R, OOS (last 12 mo) **+0.151R**.
- **Cost stress:** +0.110 (2pt) → +0.070 (4pt) → +0.030 (6pt) — survives, thins.
- **Caveat (honest):** the edge is **long-skewed** (+0.199R long vs +0.018R short)
  in a bull-heavy sample. In a sustained down-regime the long side will suffer —
  do **not** switch to long-only (it just hides the bet).

## The frontier — where is 80%? (best strategy)
`pass% / blow%`, by deadline × per-trade risk:

```
 deadline | r=0.50% r=0.75% r=1.00% r=1.25% r=1.50% r=2.00% r=2.50%
     1wk |    0/0     1/0     2/0     4/0     5/1     5/12    5/58
     2wk |    1/0     5/0    11/0    15/6    19/14   22/36   13/79
     3wk |    3/0    11/1    19/6    26/14   30/24   32/46   15/83
     4wk |    5/0    16/3    27/11   34/21   38/31   37/52   16/84
     6wk |   11/1    26/8    37/20   44/30   46/39   40/57   16/84
     8wk |   17/2    34/13   45/25   50/35   50/44   41/58   16/84
    12wk |   29/6    46/20   54/32   55/40   52/46   41/59   16/84
```
**The pass rate ceilings around 55% (12 weeks, ~1.25% risk) and never reaches 80%
at any deadline or risk.** At the 3-week target it is 32% at best.

## Why >80%-in-<3-weeks is impossible (the proof)
To make +10% in ~15 trading days while never losing 3% in a day or 10% overall,
the daily return stream needs a **daily Sharpe ≈ 1.0**. Sweeping a clean normal-day
model through the exact FTMO rules:

```
 daily Sharpe -> 15-day pass%
   0.05  -> 22.8%   (<- what the best real strategy actually has)
   0.20  -> 34.0%
   0.50  -> 58.0%
   0.75  -> 73.8%
   1.00  -> 84.7%   (<- first crosses 80%)
```

The best strategy's **actual daily Sharpe ≈ 0.056** (mean +0.22%/day, std 3.9%/day
at 2% risk; annualized ~0.9). Reaching 80%-in-3-weeks needs ~**18× that** — a daily
Sharpe near 1.0 (annualized ~16), which is HFT-market-making territory, not a
directional intraday edge on one CFD after costs. The fat-tailed payoff that *makes*
the edge is the very thing that keeps the daily Sharpe low and trips the consistency
rule. Speed (high variance) and 80% reliability (low variance) are mutually exclusive
with a thin, fat-tailed edge.

## Honest recommendation
- **There is no legitimate >80%/<3-week strategy.** Anything claiming it is curve-fit
  or ignoring the daily/overall limits on floating equity.
- **Best realistic plan:** run the strategy above at **r = 1.0–1.25%** and give it
  **8–12 weeks** → ~50–55% pass with ~25–35% blow-up. That is the honest ceiling for
  a real NAS100 edge under these rules.
- **If you insist on a 3-week sprint:** r = 2%, ~32% pass / ~46% blow — a gamble,
  sized as money you can lose. Lower-risk 3-week attempts are safer but pass <20%.
- **Reproduce:** `python3 scoreboard.py`, `python3 frontier.py`.
