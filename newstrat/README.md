# newstrat — a new challenge strategy: higher frequency / higher pass, honestly

Brief (from the user): **I** find the strategy; target **higher frequency, lower RR, higher win
rate, higher pass rate**; try the sweep edge but don't force it; test on **all 5 instruments**
(NAS100 + EURUSD/GBPUSD/AUDUSD/USDJPY). Same discipline: train/test/k-fold, cost-inclusive, and
call out anything that only works in-sample. Running as a self-paced research loop.

Honest framing up front: the project has repeatedly found **pass rate is driven by HIGH-RR /
low-frequency structure**, and low-RR/high-WR fails when the setups have no edge. The only path to
"higher frequency AND higher pass" is spreading frequency across **uncorrelated instruments** (so
the portfolio trades more often but no single instrument slams the 3% daily cap) — *if* each
instrument carries real edge. So the plan: find where edge exists across all 5 instruments, keep
the high-RR structure that carries it, and stack the uncorrelated ones for frequency + smoothness.

## Iteration 1 — edge vs RR across all instruments (`allinstr.py`, `scan.py`)
Session-open breakouts, ATR-scaled stops, real cost, RR swept 1.5→4 on each instrument.

| instrument | edge? | RR behaviour |
|---|---|---|
| NAS100 | yes (small) | +EV only at **3–4R**; dies at low RR |
| USDJPY | yes (small) | −0.02 at 1.5R → **+0.03/+0.04 at 3–4R** (both Tokyo & London) |
| EURUSD | no | flat −0.09..−0.14 at every RR |
| GBPUSD | no | flat −0.05..−0.10 (best −0.04 at usidx 2.5R, still negative) |
| AUDUSD | no | strongly negative −0.16..−0.23 everywhere |

**Verdict: lower RR helps NOWHERE.** The two instruments with edge (NAS100, USDJPY) have a
*momentum* edge whose value is entirely in the fat right tail — taking profit early (higher WR,
lower RR) **turns the edge negative**. USDJPY is the cleanest demonstration: WR 44% @ 1.5R is −EV,
WR 29% @ 4R is +EV. So the user's target profile (lower-RR/higher-WR) is structurally incompatible
with the edge these markets have. Confirmed across all 5 instruments, not just NAS100.

**Pivot (honoring "don't force stick on it"):** the real objective is higher *pass rate*.
Lower-RR was the hypothesized means and it's dead. Higher pass comes from **more uncorrelated
high-RR edges**, so next iterations hunt edge with OTHER setup types (sweep-reclaim, etc.) across
all instruments — if e.g. forex pairs carry a sweep edge even though they lack a breakout edge,
that adds decorrelated frequency and is the real path to higher pass.

## Iteration 2 — prior-day regime × setup × instrument edge matrix (`regime_matrix.py`)
User's idea: multiple strategies, one per regime, regime detected from the PRIOR day (causal —
regimes persist). Standard untuned thresholds (ADX 25/20, chop 45/55); momentum(4R) vs fade(MR),
expR reported TRAIN/TEST per cell. A cell only counts if BOTH halves are clearly +.

| instrument · prior-day regime | setup | expR train/test | verdict |
|---|---|---|---|
| **NAS100 · range** | **fade (MR)** | **+0.11 / +0.20** | real — MR works *after a range day* |
| NAS100 · unclear | momentum | +0.09 / +0.01 | weakly real (the 52p bulk) |
| **USDJPY · range** | **momentum** | **+0.09 / +0.11** | real |
| USDJPY · unclear | momentum | +0.06 / +0.06 | real |
| EUR / GBP / AUD (all regimes) | either | flip or negative | dead |

Key: "fade is dead" is **only true unconditionally** — *conditioned on a prior-day range regime*,
NAS100 mean-reversion has real OOS edge. Momentum on USDJPY works in range/unclear but fails after
trend days (contrarian-after-trend). So prior-day regime routing does carry real signal.

## Iteration 3 — does routing ADD pass rate? (`router.py`)
Per-leg: **NAS100 fade|range = 55% WR, +0.140 expR** (higher WR *and* edge than 52p — exactly the
target profile, and it held OOS). But it fires only **0.15×/day**. Stacked on 52p (risk on train,
4-fold):

| combo | TEST pass | worst fold |
|---|---|---|
| 52p baseline | 50.6% | 37.0% |
| 52p + NAS fade\|range | 50.6% | 37.5% |
| 52p + USDJPY mom | 48.6% | 38.0% |
| 52p + both | 48.6% | 39.3% |

**Verdict: the regime idea surfaces genuine edges (incl. a real 55%-WR one), but they're too
LOW-FREQUENCY to lift the mean pass — they only nudge the worst-fold floor (37→39).** The problem
is never edge quality, always frequency: the high-WR edge exists but is rare (needs its regime).
The ~55% ceiling holds. Next: can the fade-in-range / sweep edges be made higher-frequency without
diluting (one honest attempt), or is the ceiling structural.

## Iteration 4 — can the high-WR edge be made higher-frequency? No. (`freq_scale.py`)
Tried to scale the 55%-WR fade|range edge: loosen the range threshold (more days) and fade more
aggressively (lower k). Result — it does NOT scale:

| range def | /day | expR train / test |
|---|---|---|
| strict (ADX<20 & chop>55) | 0.15 | **+0.112 / +0.197** (holds) |
| chop>q60 | 0.40 | −0.043 / +0.057 (train flips) |
| chop>q40 | 0.61 | −0.118 / +0.054 (train flips hard) |
| chop>median | 0.50 | −0.054 / +0.116 (train flips) |

Every attempt to raise frequency turns TRAIN expR negative — the marginal days added are losers,
and the positive test numbers are noise (train↔test sign-flip = no robust edge). The edge exists
ONLY on true range days (~15% of days, one trade each). **Confirmed: real edges here are rare by
nature and forcing frequency dilutes them to noise** — same as the sweep-frequency test in
`../regimeswitch`. The target higher-freq + higher-WR + higher-pass is not achievable on these
instruments because the high-WR edges are structurally low-frequency.

## Iteration 5 — sweep-reclaim across all instruments: doesn't generalise (`sweep_all.py`)
Generalized sweep (prior-day + pre-session H/L, trend-open gated) on all 5 instruments: expR
NAS100 −0.13/+0.04 (flip), EUR −0.06/−0.09, GBP −0.04/−0.14, AUD −0.15/−0.01, JPY −0.17/+0.05
(flip). **Nothing holds.** No forex pair has a sweep edge, and the multi-level version doesn't even
reproduce NAS100's +0.24 — that was specific to the exact pre-open-range construction; adding
levels dilutes it. Sweep is NAS100-specific, construction-specific, and low-frequency.

## CONVERGED — final verdict
Five iterations, one wall every time:
1. **Lower RR fails everywhere** — the edge on the two instruments that have one (NAS100, USDJPY)
   is high-RR momentum; cutting winners short for a higher WR turns it negative.
2. **Prior-day regime routing finds REAL edges** — NAS100 fade|range (55% WR, +0.14, held OOS) and
   USDJPY momentum|range+unclear — so the user's regime idea genuinely works.
3. **But those edges are low-frequency and DON'T SCALE** — loosening thresholds to raise frequency
   flips train expR negative (marginal days are noise). Confirmed for fade|range and sweep alike.
4. **No cross-instrument edge beyond NAS100 + USDJPY** — EUR/GBP/AUD are dead in every test.

**So the target (higher frequency + higher WR + higher pass) is not achievable on these 5
instruments** — because the high-WR edges that exist are structurally rare, and forcing frequency
dilutes them to noise. The ~55% (1-month) / ~72% (2-month) ceiling is real.

**What the search DID produce (worth keeping):** the NAS100 **fade-in-range** leg — a genuine
55%-WR, +0.14 edge, decorrelated from 52p — is a legitimate small add-on that lifts the worst-fold
floor (37→~39). It doesn't raise the mean, but it's the highest-WR edge the whole project found.

**Bottom line: 52p (NAS100 momentum) at 0.5-0.6% remains the best challenge strategy** (~72% over
2 months). The regime work confirmed the ceiling is structural, not a failure of effort — and gave
one keeper floor-raiser. Binding constraint = the instrument set; a genuinely new market with its
own intraday edge is the only thing that could push further.

## Deliverable — `ChallengePhase52pRegime.py` (52p, regime-optimised)
Requested: duplicate 52p and optimise it with regime switching. Tested honestly (`regime_optimize.py`)
across three forms:
- **switch** (replace momentum with fade on range days): WORSE — safer (lower blow) but loses too
  much frequency, pass drops on every horizon (2mo 71.7→69.4%). Rejected.
- **add** (keep all 4 momentum legs, ADD the fade leg on prior-day-range days only): the winner.

`ChallengePhase52pRegime.build(df)` = the 4 unchanged 52p momentum legs + a fade leg gated to
prior-day-range regime (ADX<20 & Chop>55, causal). Honest result:

| horizon | 52p base | + regime | Δ |
|---|---|---|---|
| 1 month | 55.3% | 55.7% | +0.4 |
| 2 months | 71.6% | 72.0% | +0.4 |
| 3 months | 80.5% | 80.9% | +0.4 |

WR 26.8→27.9%, expR +0.089→+0.091, blow slightly lower — a **small but consistent** lift on every
horizon. It's small because the fade|range edge (the project's highest-WR find at 55%) is real but
low-frequency (~0.15/day). That is the honest ceiling: regime switching optimises 52p a little, not
a lot. Regime detection is iADX(14)+Choppiness(14) on D1 — portable to the .mq5 EA on request.

## Iteration 6 — DATA-FIRST mining (`mine.py`, `mined.py`)
Brief: stop testing known templates; analyse the data, find patterns, CREATE the strategy.
Protocol: pattern selection on TRAIN only at |t|≥3.5 (multiple-testing corrected), one-shot
sign-check on TEST, then an **economic-mechanism check** (spread column) before believing anything.

**The two flashiest finds were artifacts** — the strongest statistics in 9M bars:
- FX 00:45 "pop" (t up to **57**, held OOS, all pairs): the rollover spread renormalizing on
  bid-price bars (spread 29–56pts → 11–16 at exactly 01:00). Buying pays the wide ask; fake.
- GER40 22:45 "fade" (t=−17.7, held OOS): spread 60 → **810** at 23:00; the bid is mechanically
  crushed into the close. Fake.
Lesson: t-stats + OOS holds are NOT enough — the *mechanism* must survive the microstructure.

**Clean survivors** → a 6-leg time-of-day drift portfolio (NAS 10:15L/17:30S/18:15L/22:45L,
GER40 09:00L/18:00L; time exits, 0.25-ATR protective stops): **5.9 trades/day, WR 50.5%,
expR −0.000 — exactly 0EV after cost.** The requested high-freq/high-WR/low-RR shape, honestly
mined. MC: alone **20.6% pass / 75.6% blow** (the daily-cap slam, again — 4th confirmation that
this structure is the worst for prop challenges); stacked on 52p it *drags* (49→45%).

**One keeper:** G2 = GER40 long 18:00→18:45 (into the DAX cash close; spread flat, +0.028/+0.066
both halves, 55% WR). 52p + G2 only: TE 49.2→50.1%, foldMean 55.5→56.3%, worst 37.4→38.4% —
a small, consistent, decorrelated (+0.08) lift, same size as the fade|range keeper.
