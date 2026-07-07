# challengephaseHF — testing the low-RR / high-win-rate / high-frequency idea

Goal: maximize the **monthly (20 trading day) pass rate** on the FTMO $15k 1-Step by
stacking many uncorrelated, high-win-rate, sub-1 reward-to-risk, high-frequency setups
built from published SSRN intraday research.

**Verdict up front: the idea does not work on NAS100, and it is not close.** The low-RR
portfolio passes ~1% of the time in a month; a normal higher-RR combo passes ~38%. The
reason is simple and structural: **monthly pass rate is driven by expectancy, and every
low-RR/high-WR setup here is net-negative after costs.** You cannot diversify or
out-frequency a negative edge.

## What was built (grounded in SSRN)
`hf_strats.py` implements seven setups from the literature:
- **mr_z, revN, rsi2, bbfade** — intraday mean reversion / short-term reversal (Brogaard-
  Han-Kim 2024; Miwa; Bhatti regime-Z; Connors RSI(2); Bollinger). The low-RR/high-WR core.
- **mim** — Market Intraday Momentum (Gao-Han-Li-Zhou, JFE 2018): first 30-min return sign
  drives a late-session trade.
- **gaprev** — Overnight-Intraday Reversal (Liu-Liu-Wang-Zhou-Zhu): fade the open gap.
- **orfade** — opening-range failed-breakout fade.

`improve.py` sweeps geometry and adds selectivity + a flat-regime filter. `final.py` does
edge, correlation, the portfolio Monte-Carlo, and the head-to-head vs a higher-RR baseline.

## The setups DO hit the requested profile
| setup | trades/day | win rate | RR | expR (after 2pt cost) |
|---|---|---|---|---|
| mr_z | 13.0 | 55.6% | 0.63 | **−0.059** |
| revN | 22.8 | 55.8% | 0.63 | **−0.058** |
| rsi2 | 11.2 | 57.5% | 0.59 | **−0.058** |
| bbfade | 10.1 | 58.6% | 0.60 | **−0.043** |
| mim | 0.9 | 46.4% | 0.97 | −0.061 |
| gaprev | 0.9 | 50.1% | 0.94 | −0.028 |
| orfade | 1.0 | 58.0% | 0.56 | −0.087 |

High win rate, RR under 1, frequent trades. Exactly the target. **And every single one
loses money after costs.**

## Why it fails (three findings)
1. **The signal has zero real edge.** Sweeping the take-profit from 0.4R to 3.0R moves the
   win rate from 60.6% down to 44% and RR from 0.5 up to 1.05, but **expR stays glued to
   −0.058 the whole way.** A flat-negative expectancy across every geometry is the exact
   signature of a coin-flip signal that only ever loses the cost. There is no TP that
   turns a no-edge fade into a winner.
2. **Sub-1 RR needs a win rate the market will not give.** After the 2pt round-turn on a
   tight ~20pt take-profit, breakeven needs ~65-70% wins. Efficiently-priced NAS100
   intraday reversion delivers ~55-58%. The gap is permanent, and selectivity + a
   flat-regime filter closes only a point or two, never enough.
3. **The "diversification" is half illusion, and cannot save a negative edge anyway.** The
   four mean-reversion setups are correlated with each other (mr_z/bbfade 0.66, mr_z/rsi2
   0.54): they are four versions of the same fade, not four independent edges. The genuine
   decorrelators (mim, gaprev, orfade, all ~0.0 correlation) are also net-negative.
   Stacking negative-edge, partly-correlated strategies just produces a smoother losing
   curve. **You cannot diversify your way out of negative expectancy.**

## The head-to-head (monthly pass, out-of-sample)
| approach | edge | 20-day pass | blow | median days |
|---|---|---|---|---|
| **low-RR/high-WR portfolio** (7 setups stacked) | expR < 0 | **1.4%** | **99%** | — |
| **higher-RR baseline** (ORB 50 4R + VWpull 40 4R) | expR **+0.039** | **38.5%** | 48% | 8 |

The higher-RR combo wins by **27x** on monthly pass. It has a *small but positive* edge,
because letting a low-WR strategy run to 4R gives it positive skew (a few big winners drag
the account to +10%). The low-RR portfolio, with negative edge, drifts into the floor and
blows 99% of the time no matter the risk level.

## Honest takeaways
- **Monthly pass rate is about expectancy, not the win-rate/RR/frequency picture.** A
  pretty 58%-win-rate curve that is net-negative passes ~1%. An ugly 22%-win-rate curve
  that is net-positive passes ~38%.
- **Low-RR/high-WR is a funded-phase idea, not a challenge idea, and even then it needs a
  real edge.** It smooths variance, which helps bank cash when there is no target to hit.
  It cannot manufacture the drift needed to reach +10%, and here the underlying setups have
  no edge to smooth in the first place.
- **The SSRN reversal edges are cross-sectional** (long the losers, short the winners
  across *many* stocks). They do not transfer to trading one index's raw price after costs.
- **What actually raises monthly pass** (from the v2/v3 work): a genuinely positive-edge
  runner strategy, feature-filtered entries, a −2R daily circuit breaker, and risk tuned to
  the deadline. That tops out around 44-47% in 20 days, and ~38% for the plain live combo.
  That remains the honest ceiling.

## Follow-up: "you don't need edge, 0EV passes via variance" (`variance_play.py`)
This is correct, and it is the deeper reason the higher-RR combo wins. A prop challenge is
a first-passage bet; by optional stopping a driftless account reaches +10% before −10%
about 50% of the time before the deadline even applies. Testing a synthetic **exactly-0EV**
strategy (wr = 1/(1+RR)) across every variance structure under the full FTMO rules:

- **A 0EV strategy passes ~38.6% in 20 days at the optimal structure** — the same as the
  slightly-positive live combo. Edge is not required. The structure is.
- **The optimal 0EV structure is the OPPOSITE of low-RR/high-WR:** RR≈4, win rate ≈20%,
  ~1 trade/day, ~2% risk. Few big bets.
- **Why:** one trade/day at high RR makes a losing day only −2%, under the 3% daily cap, so
  ~0% of blows come from the daily limit. Low-RR/high-frequency hits the daily cap on
  every bad cluster (98–100% of blows), which is why that portfolio blew 99% of the time.
- **Sensitivity:** at the optimal structure, pass decays slowly with cost (0EV → 38.6%,
  −0.03R → 36.9%, −0.05R → 34.3%). So the game is: get close to 0EV (small cost drag) AND
  use the high-RR / low-frequency structure. The small +edge only adds a few points.

So the corrected conclusion: the earlier "low-RR/high-WR fails" is right, but the deep
reason is **structure**, not "no edge". The winning variance play is **few big bets (high
RR, low frequency), stacked across uncorrelated setups** so added frequency does not
concentrate daily-cap risk. That is exactly the v2/v3 direction, ceiling ~44–47% in 20 days.

## Acting on it: the best high-RR uncorrelated combo (`hf2_portfolio.py`, `hf2_search.py`)
Rebuilt the battery at HIGH RR across sessions + mechanisms. At high RR the setups turn
slightly positive-EV (EU-ORB +0.13, VWpull +0.10, US-ORB +0.09, even gaprev +0.05 vs
−0.028 at low RR). Correlations are mostly clean; same-session pairs correlate (US-ORB↔VWpull
0.67, US-ORB↔IB 0.70). A 4-fold CV combo search (ranked by worst fold) found the best:

**US-ORB (16:00, 4R) + EU-ORB (11:00, 4R) + VWAP-pullback (6R) + PDH/PDL (trail 3R),
−2R daily breaker, 1% risk.** 100k MC: **~52% monthly pass all-data, ~44% out-of-sample,
median 9 days** (edge WR 26.8% / expR +0.089 / PF 1.14 / 3.8 trades/day). k-fold: mean 52%,
worst fold 38.7%.

That is the best 20-day pass found in the whole project (beats the live 4R ~38–40% and the
v3 winner ~40–47%). But note the honest ceiling: **the worst CV fold (38.7%) sits right on
the 0EV structural baseline** — in a bad regime the edge collapses to what pure variance
would give. Adding a 5th/6th leg did not help (extra daily-cap exposure offsets the
decorrelation). So the monthly-pass ceiling on NAS100/FTMO is ~50% (the 0EV martingale
limit), realistically ~44–52% for this combo and floored near 38% in a bad month. The
structure (high RR, low frequency, a few uncorrelated legs, −2R breaker) is what matters;
the small edge just lifts it a few points above the 0EV floor.
