# NAS100 FTMO $15k — fresh strategy search (v2). Results & verdict.

**Goal:** a brand-new NAS100 strategy to pass the FTMO $15k 1-Step fast, with a high
pass rate (target >80% in <3 weeks). Only the *rules* carried over from prior work;
strategies, engine and validator were rebuilt from scratch on real M1 data.

## TL;DR (updated after the scale-out breakthrough)
The decisive lever was **scale-out exits** (bank most of a winner at +2R, run a
breakeven remainder). It roughly **doubled** the pass rate by lifting the daily
Sharpe from ~0.06 to ~0.31. The final **2-setup scale-out combo** (cost 3pt,
validated OOS and every year 2022-25):

| deadline | r=1.00% (safe) | r=1.25% (faster) |
|---|---|---|
| 3 weeks | 58% pass / 1% blow | **64% / 6%** |
| 4 weeks | **73% / 1%** | 76% / 7% |
| 5 weeks | **82% / 1%** | 82% / 8% |
| 6 weeks | 87% / 1% | 86% / 9% |
| 8 weeks | 94% / 2% | 89% / 9% |

- **>80% in <3 weeks is still not reached** (~64% there) — that exact corner needs a
  daily Sharpe ~1.0 and we have ~0.31. But **80% is reachable at ~5 weeks with ~1%
  blow-up**, which was impossible with every earlier approach.
- The early part of this doc (the breakout-only families that ceiling ~32%) is kept
  as the research trail; the **recommended strategy is the scale-out combo** below.

## Data, engine, validator (all rebuilt)
- **Data:** real FTMO MT5 **US100 M1**, 1,042,353 bars, **2022-10-18 → 2025-10-01**,
  99.9% clean. Timezone confirmed **EET/EEST (FTMO server)** from the volume profile
  (US cash open lights up 16:00-17:00 server) → 00:00 = the FTMO daily reset.
- **Costs:** modeled **2-3 points round-turn**, stress-tested to 6. R-/%-based sim so
  currency/point-value cancel.
- **Engine (`engine.py`):** M1 fills, next-bar-open entry (no look-ahead),
  STOP-before-TP within a bar, per-trade **MAE/MFE**, and **scale-out** (partial at a
  target, runner to breakeven + trail).
- **Validator (`ftmo.py`):** bootstraps whole **trading days** and enforces all five
  rules on **floating** equity: +10% target, static $13,500 floor, 3% daily loss,
  min-4-days, and the 50% best-day consistency rule. Risk compounds off current
  balance; optional adaptive sizing.

## The loop — what each family showed
```
STRATEGY                       WR     expR   | 3wk pass  blow   note
MeanRev: VWAP-fade / OR-fade   ~45%   <0     |   <17%    high   loses after costs (NAS trends)
Breakout: London ORB           25%    -0.07  |   18%     69%    no EU-session edge
Breakout: US ORB (trail only)  31%    +0.11  |   32%     46%    real edge, but thin & fat-tailed
  + volume filter              31%    +0.11  |   32%     46%    small free gain (kept)
Combo US16:00+US16:30          32%    +0.08  |   29%     30%    cuts blow, not pass (correlated)
VWAP trend-pullback (s40)      27%    +0.10  |   30%     32%    NEW positive, different signal
** SCALE-OUT US ORB            36%    +0.42  |   59%     15%    the breakthrough
** SCALE-OUT COMBO (A+B)       36%    +0.37  |   64%      6%    recommended
```
Findings: mean-reversion loses; only US-open momentum has a durable edge; the edge
lives in the fat tail, which a wide trail *gives back* — and that is exactly what the
**scale-out fixes** by banking the frequent +2R pokes while keeping a free runner.

## The recommended strategy (`recommended.py`)
A 2-setup combo, US cash session, one trade/day each, flat by 22:55 server, no Friday
entries. **Risk 1.00%/trade** (≤2 trades/day → ≤2% daily, well under the 3% cap).

**Setup A — US opening-range breakout, scale-out.** Server 16:00, mark the first
15-min range. Enter the first break (long > high / short < low) when the breakout
bar's volume beats the opening-range average. **50-pt stop = 1R. Scale 2/3 out at
+2R**; move the last 1/3 to breakeven and trail it 3R behind the extreme.

**Setup B — VWAP trend-pullback, scale-out.** Build the session VWAP from 16:00. In
an uptrend (price > VWAP, VWAP rising) buy a dip that tags VWAP and closes back above
(mirror for shorts). **40-pt stop = 1R. Scale 1/2 out at +2R**; runner to breakeven +
trail 3R.

**Edge:** expR **+0.37**, PF 2.2, WR 36%, ~10 trades/wk, daily Sharpe ~0.31.

**Validation (robust):**
- **Every year positive:** 2022 +0.50, 2023 +0.28, 2024 +0.40, 2025 +0.33.
- **Both directions:** long +0.38, short +0.31.
- **Out-of-sample** (last 12 mo, never used to pick params), 4pt cost: 3wk 63% / 4wk 75%.
- **Cost stress:** edge survives to 6pt.

## Why this works (and where the wall still is)
Scale-out converts a low-WR, fat-tailed payoff (daily Sharpe 0.06) into a
higher-WR, smoother one (0.31) by realising the common +2R move instead of trailing
it back to a loss. That ~5× Sharpe gain is what moves the frontier. But 80%-**in-3-
weeks** needs daily Sharpe ~1.0 (normal-day model through the exact rules: Sharpe
0.31→~60% pass at 15 days, 1.0→85%), so the 3-week/80% corner remains out of reach
for a single-instrument directional edge — while 80% at **5 weeks** is now solid.

## Recommendation
- **Best plan:** run the combo at **r = 1.00%** → ~73% pass in 4 weeks, ~82% in 5,
  ~1% blow-up. This is the safe, high-probability route.
- **Faster:** r = 1.25% → ~64% in 3 weeks at ~6% blow-up.
- **Live caveat:** these assume limit-fill partials and breakeven runners; real fills
  slip, so expect somewhat lower live — 1.00% sizing leaves margin. Re-validate on
  your own fills via the journal once running.
- **Reproduce:** `python3 recommended.py` · `python3 optimize.py` · `python3 scoreboard.py`.
