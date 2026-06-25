# NAS100 FTMO $15k — fresh strategy search (v2). Results & verdict.

**Goal:** a brand-new NAS100 strategy to pass the FTMO $15k 1-Step fast, with a high
pass rate (target >80% in <3 weeks). Only the *rules* carried over from prior work;
strategies, engine and validator were rebuilt from scratch on real M1 data.

## TL;DR (updated: scale-out + a 3rd decorrelated setup)
Two levers broke the old ~32% ceiling: **scale-out exits** (bank most of a winner at
+2R, run a breakeven remainder) lifted daily Sharpe ~0.06→0.31; then a **3rd,
negatively-correlated selective range-fade** lifted it to ~0.37 and pushed the 80%
mark from ~5 weeks down to ~4. Final **3-setup scale-out combo** (cost 3pt, validated
OOS and every year 2022-25), per-trade risk **1.0%**:

| deadline | r=0.90% | r=1.00% | r=1.25% (cap-risky) |
|---|---|---|---|
| 3 weeks | 63% / 2% | **67% / 2%** | 67% / 15% |
| 4 weeks | 77% / 2% | **81% / 2%** | 76% / 16% |
| 5 weeks | 86% / 2% | **88% / 3%** | 80% / 16% |
| 6 weeks | 91% / 2% | 92% / 3% | 81% / 17% |
| 8 weeks | 95% / 3% | 95% / 3% | 82% / 17% |

- **80% is now reached at ~4 weeks** (81% / 2% blow) — it was unreachable at any
  deadline with the earlier breakout-only approach.
- **>80% in <3 weeks is still not reached** (~67%): that corner needs daily Sharpe
  ~1.0 and we have ~0.37. The 3-week number nearly doubled (32%→67%).
- **Daily cap (3%) drives sizing:** 3 trades/day, so keep r ≤ ~1.0% — three full stops
  must stay under 3% (the r=1.25% column shows the breach: blow-up jumps to ~16%).
- **Consistency (50% best-day)** costs only ~1pp — scale-out caps single-day spikes.
- The early part of this doc (breakout-only, ceiling ~32%) is the research trail; the
  **recommended strategy is the 3-setup scale-out combo** (`recommended.py`).

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

**Setup C — selective range-fade, scale-out (the decorrelator).** ONLY when VWAP is
flat (a range day, |VWAP slope| small), fade a >2σ stretch from VWAP back toward it.
**40-pt stop = 1R. Scale 1/2 out at +1R**; runner to BE + trail 2R. Standalone edge
+0.16R, WR 48%, and **−0.11 correlation** with A+B — it wins on the chop that the
trend setups give back, which is what lifts the combo's daily Sharpe.

**Edge (A+B+C):** expR **+0.30**, PF 2.0, WR 40%, ~15 trades/wk, daily Sharpe ~0.37.

**Validation (robust):**
- **Combo positive every year:** 2022 +0.50, 2023 +0.28, 2024 +0.40, 2025 +0.33;
  the fade leg is +0.18/+0.15/+0.11 in 2023/24/25 (flat in the violent 2022 bear).
- **Both directions** positive on all three setups.
- **Out-of-sample** (last 12 mo, never used to pick params), 4pt cost: 3wk 66% /
  4wk 78% / 5wk 85% — matches the full sample.
- **Cost stress:** edge survives to 6pt.

## Why this works (and where the wall still is)
Scale-out converts a low-WR, fat-tailed payoff (daily Sharpe 0.06) into a
higher-WR, smoother one (0.31) by realising the common +2R move instead of trailing
it back to a loss. That ~5× Sharpe gain is what moves the frontier. But 80%-**in-3-
weeks** needs daily Sharpe ~1.0 (normal-day model through the exact rules: Sharpe
0.31→~60% pass at 15 days, 1.0→85%), so the 3-week/80% corner remains out of reach
for a single-instrument directional edge — while 80% at **5 weeks** is now solid.

## Pre-deploy tweaks tested — none beat the baseline (`improve.py`)
Tested rigorously under the FTMO MC (OOS + per-year) before deployment:
| idea | verdict |
|---|---|
| **ATR-scaled stops** (scale stops by recent vol) | **neutral once look-ahead removed.** With a *full-sample-median* denominator it looked great (OOS blow 6%→1%) — but that peeks at future vol. With a trailing ATR(14)/ATR(100) denominator (what the EA can compute live) it's identical on pass and slightly worse at r=1.25%. **Kept OFF.** |
| ATR regime filter (skip top-10% vol days) | lowers blow but costs more pass — net worse |
| HTF 20-day trend filter on A,B | **hurts badly** (4wk 80%→58%): kills good counter-trend session breaks (matches prior research) |
| Fade-only-on-normal-vol | ~neutral (slightly higher expR, slightly lower pass) |
The fixed-stop baseline is already at a solid local optimum; these knobs don't add
edge. The look-ahead lesson is the main takeaway — validate scalers trailing-only.

## Recommendation
- **Best plan:** run the 3-setup combo at **r = 1.00%** → ~67% pass in 3 weeks, ~81%
  in 4, ~88% in 5, with ~2-3% blow-up. Do **not** exceed ~1.0%: 3 trades/day means
  three stops must fit under the 3% daily cap (r=1.25% breaches and blow-up jumps to
  ~16%).
- **Simpler/safer:** the 2-setup variant (A+B, no fade) is ~80% at 5 weeks with only
  2 trades/day and more daily headroom — fewer moving parts to run live.
- **Live caveat:** these assume limit-fill partials and breakeven runners; real fills
  slip, so expect somewhat lower live — 1.0% sizing leaves margin. Re-validate on your
  own fills via the journal once running.
- **Reproduce:** `python3 recommended.py` · `python3 optimize.py` · `python3 scoreboard.py`.
