# v3 — fresh strategy loop (new signals, ensembles, swing). 4-week focus.

Built on the **bug-fixed** v2 engine/MC (partial-accounting fix + conservative
intra-bar trailing). Goal: beat the corrected ~38-40% / 4-week ceiling. Re-read all
new code for look-ahead; fixed one operator-precedence bug in the swing breakout.

## What was tried and what it gave (4-week pass, cost 3pt)
| family | best 4wk pass | note |
|---|---|---|
| **ORB + VWAP-pullback, 4R TP** (v2 carry-over) | **~39%** | still the best |
| gap-and-go / gap-fade (overnight gap) | 32% | thin edge (+0.02R) |
| volatility-expansion breakout | 29% | thin (+0.05R) |
| power-hour continuation | 18% | negative expR |
| narrow-range breakout | 10% | good expR but too few trades |
| ensembles (ORB+pull+gap+volx) | ~38% | mixing cuts blow-up, not pass |
| **swing trend / breakout (daily bars)** | **~14%** | far worse — see below |

## Why nothing beats ~40% (now proven from three independent angles)
1. **Daily Sharpe** (pressuretest.py): 50%/4wk needs daily Sharpe ~0.35-0.40; the best
   NAS100 edge has ~0.05. ~8x short.
2. **Stacking / ensembles**: extra setups are correlated or edgeless — combining lowers
   variance (blow-up) but not drift (pass), so pass stays ~38-40%.
3. **Swing** (daily_swing.py): to make +10% in 4 weeks you need ~1x+ leverage, but at
   that leverage a normal **-3% NAS day breaches the 3% daily cap**. Safe (wide-stop)
   sizing makes per-day R too small to reach +10% (0% pass / timeout); aggressive
   sizing blows up 55-80%. Max swing 4wk pass ~14%.

**The 3% daily cap vs NAS100's volatility-to-edge ratio is the hard wall** — it limits
deployable leverage below what +10%-in-4-weeks requires, for intraday *and* swing.

## Honest best (deployable)
Unchanged from corrected v2: **US ORB (16:00, 15m, 50pt stop, vol-confirmed) + VWAP
trend-pullback, both hard 4R take-profit**, 1 trade/day each, EOD-flat, Fridays on,
risk ~1.0%. **~39% pass in 4 weeks (~34% in 3, ~47% in 8)**, blow-up 40-47%.

## Second instrument: GOLD (XAUUSD, 22yr M1) — uncorrelated but NO durable edge
- Gold daily returns are **uncorrelated with NAS** (+0.05) — exactly what stacking needs.
- The true minute-aligned **NAS+Gold combo cuts blow-up hard** (4wk 52%→31%) but **does
  not raise 4-week pass** (39% vs NAS 41%): combined daily Sharpe only 0.04→0.046. Two
  instruments is far short of the ~8 uncorrelated edges needed for Sharpe ~0.4.
- **The 22-year history is decisive: gold has NO durable intraday edge.** Every signal
  (ORB at 10:00/15:30/16:00, pullback, long-only, fade) is **negative over 2010-2026**
  (-0.03 to -0.05R, most 3-year blocks negative). The +0.089R I first saw was only
  2023-25 — a regime fluke. The long data prevented recommending a fluke (same class of
  error as the earlier engine bugs).
- Net: gold can't supply a reliable second edge. The combo's lower blow-up came from
  adding a ~zero-edge uncorrelated stream (variance down, no durable drift, drags long-run).

## Gold-specific strategies (different styles) — also no durable edge
Tried gold-native styles, not just the US-open ORB, scanned over 2010-2026:
Asian-range breakout (cont) ~0.00R (2/5 blocks +), Asian fade -0.08 (0/5),
trend-continuation -0.03 (1/5), counter-trend -0.03 (0/5). **None durable.** Gold
is intraday-efficient in OHLCV across every family tested (8+).

**Mix-and-match verdict:** with no gold edge, the combo can only reduce variance. At
matched risk the combo edges NAS (37% vs 34% at r=0.75%), but 3 trades/day caps it at
~0.75% (above that, 3 losers breach the 3% daily cap), while NAS-only at r=1% reaches
**41%/4wk**. So mixing does not beat NAS-only on 4-week pass. Best deployable stays
NAS ORB+pullback, 4R TP, r=1.0% (~41%/4wk, ~47% blow).

## The only real ways past ~40%
- A **different instrument** with M1 data (FX, gold, another index) to find a second
  *uncorrelated* edge to stack — the one lever that raises daily Sharpe. Need the data.
- A **5% daily-loss** product instead of 3% — materially changes the leverage math.
- Accept ~40%/4wk and run repeatedly (fee refunds on first payout).

`>50%/4wk is not attainable on NAS100 alone under a 3% daily cap.` This is the honest
result after intraday, ensemble and swing searches, with the engine bugs removed.

## Monthly-pass / barrier-math (per the prop-firm-math video)
Reframed for MONTHLY (4-week) pass rate (WR irrelevant), with the convex payoff in mind.
- **Barrier math (synthetic, definitive):** a clean 1:1 strategy sized to the daily-cap
  edge (r=2.5%) crosses **>50% monthly pass only at WR>=~54-55%** (expR ~+0.10R):
  WR50%->40%, WR55%->57%, WR60%->68%, WR65%->85%. So >50%/4wk REQUIRES WR~55% at 1:1.
- **NAS reality:** the best 1:1 NAS entry caps at **WR ~53.5%** (ORB o16:30 s80 / or60 s50),
  and real intraday variance (EOD exits + winner MAE) exceeds the clean synthetic, so it
  yields only ~24% at high risk. Pushing risk to the cap just blows up (asymmetric rules:
  consistency + min-4-days + 3% daily make the barrier sub-50% even at zero-EV).
- **Best honest monthly pass:** ORB+pullback 4R-TP, r=1% -> **~41% pass, median 8 days**
  (median <4wk MET); r=0.75% -> 36% / 27% blow. >50%/4wk NOT reachable on NAS/Gold.
- **Convex payoff (the video's real point) HOLDS:** even ~40% pass is strongly net +EV
  (fee capped ~$89, payout realized) ~ +$400-550 per attempt, ~$5k/yr over ~13 attempts.
  Median pass time is well under 4 weeks; only the >50% pass-rate target is out of reach
  under FTMO's 3% daily cap + 10% target + consistency.
