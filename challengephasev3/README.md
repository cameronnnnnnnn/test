# challengephasev3 — "combine everything, test every combination" for 20-day pass

Goal: throw every setup and lever tried across the whole project at ONE metric —
**pass rate within 20 trading days (1 real month)** under FTMO 1-Step — and find the
best, plus test the user's idea of **trading only higher-volume days via GARCH**.

**Headline (honest):** the diversified, cross-validated best is **~47% pass in 20 days**
(EU-ORB + US-ORB + VWAP-pullback, −2R breaker, 1% risk; robust across time folds, worst
fold ~36%). That confirms — for the third time, now exhaustively — the **~44% structural
ceiling** for honest diversified strategies on NAS100 under the 3% daily cap. **GARCH
day-filtering does not help this objective** (it starves the deadline of trades). A
pullback-concentration variant backtests higher (~59% mean) but bets everything on one
signal; treated as speculative, not recommended.

## Files
- `garch.py` — GARCH(1,1) rolling 1-step conditional-vol forecast per day (look-ahead
  free, cached), a trailing-percentile regime rank, and a validation harness.
- `search.py` — full setup library (78 variants) × geometry; simulate-once/cache; phased
  MC search (singles → levers → combos) at the 20-day deadline, train/test.
- `validate.py` — the honest re-do: **cross-family** combos only + **4-fold CV** ranked
  by **worst fold**; plus the overfit-vs-leverage probe.
- `final_mc.py` — 100k MC of the robust winner + per-fold + deadline sweep + chart.

## What was tested (the "everything")
Setups: ORB at both US opens (16:00 & 16:30) and the EU open (11:00), OR 15/30m, stops
40–60, TP 3–6R, BE; VWAP pullback (stop 40/50, TP 3–8R, ±trail); OR-fade; VWAP-fade;
selective range-fade; PDH/PDL; liquidity **sweep**; **CUSUM** momentum-burst (±trend
filter); open-drive; IB-break. Levers: GARCH vol-regime day filter (none/low/high),
−1.5/−2/−2.5R daily circuit breaker, per-trade risk sweep. Metric: 20-day pass, TRAIN/TEST
+ 4-fold CV.

## GARCH result (the user's idea — tested both directions)
1. **The forecast works:** GARCH 1-step vol forecast vs realized intraday vol → rank
   correlation **+0.42**. Volatility clustering is real and predictable.
2. **But the edge is INVERTED vs the hypothesis.** The ORB+pullback edge by forecast-vol
   tercile: **LOW-vol +0.119 expR / MID +0.046 / HIGH +0.033.** These are *calm-day*
   strategies — high-vol days whip the tight 40–60pt stops. "Trade only high-volume days"
   is backwards; if anything you want calm days.
3. **Yet filtering to ANY regime HURTS 20-day pass** (`none` 40.6% > `lowvol` 22.8% >
   `himvol` 5.8% on the pullback). Trading ~40% of days starves the 20-day deadline of the
   trades needed to reach +10% → timeouts. GARCH filtering helps *per-trade quality* and a
   *run-to-completion* objective, but is the wrong tool for a hard 20-day pass target.

## Two overfit traps caught (why the first "answer" was 71.5% and was wrong)
- **Correlated-leg stacking:** an unconstrained combo search just piled three near-identical
  VWAP-pullback variants (disguised 3× leverage on one signal). Fixed by forcing
  **cross-family** combos (one leg per setup family).
- **Selection-on-test bias:** ranking 200+ configs by the *same* test set and taking the
  max inflates the max by luck. Fixed with **4-fold CV ranked by the worst fold** — a config
  only wins if it holds in every regime.

## Robust results (4-fold CV, breaker −2R, ranked by worst fold)
Best single per family: EU-ORB 4R (min 29.5% / mean 34.4%), US-ORB 3R (28.7 / 36.1),
VWpull 8R (26.0 / 36.9). Fades / CUSUM / drive are weak for the 20-day objective.

Best **cross-family** combo: **EU-ORB + US-ORB + VWpull → worst-fold 35.6%, mean-fold
46.8%, 1% risk.** 100k all-data MC: **47.0% pass / 38.4% blow / 14.6% timeout, median 9
days**; per-fold [52.3, 39.2, 60.0, 35.6]. Deadline sweep: 15d 40.7% · 20d 47.0% · 30d
52.3% · 40d 54.2%.

**Overfit-vs-leverage probe:** the 3× pullback "stack" survives CV (min 47% / mean 59%)
and beats 1× pullback @2.25% (min 21%) — so the laddered *exits* add real value, not just
leverage. But it concentrates 100% of risk on the pullback signal via same-bar multi-entry
(fills likely overstated live). **Higher ceiling, lower trust — prototype carefully, don't
bank on it.**

## Deliverable / recommendation
**EU-ORB (11:00, 30m, 50pt, 4R, BE@1R) + US-ORB (16:00, 30m, 60pt, 3R, BE@1R) + VWAP
pullback (40pt, 8R), −2R daily breaker, 1.0% risk → ~47% pass in 20 days, median 9 days,
robust (worst fold ~36%).** A modest, honest improvement over the live 4R (~43%) from EU-open
decorrelation + the breaker + geometry tuning. It does **not** beat the ~44% ceiling in any
trustworthy way — because the ceiling is set by the 3% daily cap + needing +10% in 20 days,
not by which signal you pick. To go higher you either (a) relax the 20-day clock
(challengephasev2: ~59% run-to-completion) or (b) accept single-signal concentration risk.
