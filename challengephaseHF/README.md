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

## Mix-and-match across instruments (`fx_mix.py`, `fx_fade.py`)
Added EURUSD/GBPUSD/AUDUSD/USDJPY M1 (2021-2025) to test cross-instrument diversification.
The premise is sound and the correlation is ideal: **NAS100 is ~0 correlated with every
forex pair** (−0.02 to 0.04), far cleaner than stacking setups on one instrument. If forex
had edge, it would genuinely smooth the account and lift the pass rate.

But it does not. With ATR-scaled stops and real spread costs, **every forex setup is
net-negative** — momentum (ORB/VWpull: EUR −0.066, GBP −0.069, AUD −0.184, JPY +0.007) and
mean-reversion (fades: −0.04 to −0.16) alike. Only USDJPY momentum is ~0EV. So stacking
forex onto the NAS100 combo **hurt** it: NAS100-only 54.9% (over common days) vs NAS100 +
4 forex 35.9%. Same lesson a third time: **you cannot diversify away negative expectancy.**
Perfect decorrelation plus no edge still drags the account down.

Conclusion: **the NAS100 ChallengePhase52p combo remains the best (~52% all-data / ~44%
OOS).** Cross-instrument diversification only helps once you have a genuinely positive-edge
setup on the other instrument, and the standard intraday templates do not provide one on
forex majors (they are efficiently priced relative to the spread). Finding real forex edge
would need a different class of signal (carry, longer horizon, event-driven), not these.

## Asian-range breakout + inventing NEW strategies (`asian_break.py`, `creative.py`, `combine_new.py`)
Task: (a) test the classic Asian-range breakout, (b) *invent* genuinely new strategies rather
than reuse known templates, (c) combine anything good with NAS100 — all with train/test +
4-fold CV. **Result: one forex leg and one NAS100 seasonal survived honest scrutiny, and what
they buy is a higher worst-regime FLOOR (37%→44%), not a higher mean.** The ~52% average
monthly-pass ceiling is structural and did not break.

### Classic Asian-range breakout (forex) — the one real edge is USDJPY (`asian_break.py`, `usdjpy_probe.py`)
Overnight range over [range_start, London-open) server, break traded after, ATR-scaled stops,
real spread. Across a window grid on all 4 majors, **only USDJPY has stable +OOS edge**: the
Tokyo-session range (00:00-08:00 server = 22:00-06:00 GMT, the JPY's home hours), break after
08:00, hard 3R, 0.30-ATR stop → **expR +0.077, PF 1.14, TRAIN +0.062 / TEST +0.109**. It is a
genuine plateau (robust across break 07-09h and across the stop×TP geometry) and positive in
4 of 5 years. Honest caveats: **thin vs cost** (≈0 EV at 2× spread) and **mostly long**
(long +0.12 vs short +0.02) — it substantially rides the 2021-25 yen-carry uptrend, so the
pure mechanical (short/cost-stressed) edge is only ~breakeven+. EUR/GBP/AUD breakouts are all
net-negative (GBP's "+OOS" flips sign across the split = noise). Lesson: the Asian breakout
works only where the instrument's own session actually moves it — JPY during Tokyo.

### Five invented strategies (NAS100) — four fail, one seasonal survives (`creative.py`, `tom_probe.py`)
Genuinely new signal structures, not the ORB/VWpull/fade/RSI templates:
| invented strategy | idea | expR (all / train / test) | verdict |
|---|---|---|---|
| coil_break | volatility-compression → expansion breakout | −0.13 / −0.08 / −0.26 | fails |
| climax_fade | fade extreme tick-volume + wide-range bar | −0.11 / −0.10 / −0.21 | fails |
| sweep_reclaim | pre-open high/low stop-run + reclaim reversal | −0.05 / −0.08 / +0.01 | no edge |
| xasset_orb | USDJPY risk-on/off filter on the NAS ORB | agree beaten by its disagree control | no lead-lag |
| **tom_long** | long NAS at US open on turn-of-month (last day + first 3) | **+0.21 / +0.15 / +0.36** | **real seasonal** |

The cross-asset filter is the instructive failure: its "agree" half is *beaten* by the
"disagree" control, i.e. the split is random — there is no NAS/JPY intraday lead-lag to
harvest. **tom_long** is the survivor: it beats an all-days-long baseline by **+0.145R** (so
it is the turn-of-month seasonal, documented in the literature as month-end index/pension
inflows — not just NAS beta), consistent across 2023/24/25. Caveats: only ~3 yrs / 144 trades,
it failed the small late-2022 bear stub, and the window peaks at first-3-days.

### Combining with NAS100 — the floor rises, the mean doesn't (`combine_new.py`)
Both survivors are ~0 correlated with 52p (0.07, 0.11) and each other (−0.02) — ideal. Stacked
on one FTMO account over the 764 common days (risk picked on TRAIN, pass on TEST + 4-fold CV):
| combo | ALL pass | TEST pass | worst fold |
|---|---|---|---|
| 52p alone (NAS100) | 55.2% | 50.6% | **37.0%** |
| 52p + USDJPY Tokyo | 53.3% | 49.9% | **44.2%** |
| 52p + tom | 55.1% | 54.0% | 37.0% |
| 52p + USDJPY + tom | 54.0% | 51.0% | 43.8% |

- **+USDJPY** trades ~2 pts of *mean* for **+7 pts of worst-fold floor (37→44%)** — a
  decorrelated positive leg smoothing the bad regime. That is the metric that matters if you
  buy multiple challenge attempts (fewer catastrophic months).
- **+tom** lifts OOS *mean* 51→54% but is flat on all-data/folds, so the gain is a
  recent-bull tailwind (regime-dependent), consistent with its per-year profile.

**Honest verdict: the ~52% mean ceiling is structural and does not break** — nothing lifts the
average materially and durably. The genuine, defensible win is **worst-regime robustness**:
USDJPY's decorrelation raises the floor ~7 points. Both add-ons are **long-biased trend-riders**
(yen-carry uptrend, equity bull), so their day-to-day 0-correlation hides a shared risk-off
vulnerability — in a true risk-off month both could fade together. So: **52p remains the core**;
`tom_long` is a free NAS100-native lift in bull regimes; USDJPY-Tokyo is a separate-symbol
robustness leg with a thin, cost-sensitive edge. This is the first thing in the project that
*helps* a stacked account — and it helps the floor, exactly as the "many uncorrelated legs"
thesis predicts, just not the mean.

## Can a risk-off / short leg hedge 52p's bad days? No — and the reason converges the project (`riskoff.py`)
The long-biased add-ons share a risk-off vulnerability, so the ideal fix is a leg that PAYS when
52p bleeds. NAS100's volatility asymmetry (down-moves are faster) makes a short-only breakdown,
armed in a bearish / vol-expansion regime, the principled candidate. It fails, informatively:
- **It is the opposite of a hedge.** Every short variant is *positively* correlated with 52p
  (+0.12 to +0.31) and *loses* on 52p's worst-quintile days (−0.09 to −0.26R) while winning on
  its best days. Because **52p's worst days are choppy / low-follow-through days, not directional
  sell-offs** — and a short-momentum leg gets whipsawed on exactly those days. You cannot hedge a
  momentum book's bad days with more momentum in either direction; they share the dependency.
- **The regime filter hurts** (short|bear expR −0.04, test −0.15): 2022-25 "bearish" days were
  mostly bear-market-rally / short-squeeze days, so shorting into them got crushed. Stacked
  worst-fold barely moved (37→38-40%, inside the noise given negative OOS expR).

**This closes the "raise the floor" thread.** 52p's floor is set by *choppy months* where every
momentum leg (long and short, on NAS100) fails together. The only thing that would offset chop is
a positive-EV **mean-reversion** edge — and every MR setup in the whole project (fades, RSI2,
bbfade, vwap_fade, climax_fade) is net-negative after cost on NAS100. So the same-instrument floor
is structural (~37% worst-fold). The one lever that genuinely raised it is a **different market's**
momentum that doesn't share NAS100's chop — i.e. USDJPY (37→44%). Net convergence of the project:
**mean ~52% (can't beat), floor ~37% same-instrument / ~44% with a cross-instrument decorrelator,
and no cost-viable anti-momentum hedge exists to do better on the data available.**
