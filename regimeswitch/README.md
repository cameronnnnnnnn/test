# regimeswitch — chasing the "88% regime-switch" claim, honestly, on FTMO

Goal: reproduce (or debunk) the ~88%/20-day claim for a regime-switching bot — mean-reversion
in ranges, trend-following in trends, breakout in expansion, sweep in reversals, with ADX +
Choppiness filters to sit out unclear/choppy regimes. Kept **separate** from the shipped 52p
work, on **FTMO 15k 1-Step** rules (we're staying on FTMO). Same discipline as the rest of the
project: train(70%)/test(30%), tune only on train, k-fold, cost-inclusive, and **call out
anything that only works in-sample.** A 55% we can audit beats an 88% we can't.

## Files
- `indic.py` — ADX, Choppiness Index, EMA-slope on daily bars (shifted 1 day = causal), plus a
  first-hour intraday choppiness. The exact tools the "88%" EAs use.
- `explore.py` — first cut: baseline 52p vs choppiness-skip filters vs a regime switch.

## First-cut findings (honest)
Regime mix on NAS100 (prior-day ADX/chop, standard thresholds): ~148 trend / 112 range / 504
unclear days. Train/test 20-day pass:

| approach | passTR | passTE | blowTE | days traded |
|---|---|---|---|---|
| A. 52p baseline (all days) | 58.2% | **50.6%** | 30.9% | 763 |
| B. skip high prior-day chop | 48.6% | 42.4% | 48.0% | 613 |
| C. skip choppy opens (1h CI) | 41.7% | 51.9% | 21.0% | 610 |
| D. regime switch (momo on trend/unclear, fade on range) | 52.6% | **51.5%** | **22.7%** | 763 |
| D′. switch + SIT OUT unclear days | 6.4% | 3.6% | 34.9% | 260 |

**Two lessons up front:**
1. **Sitting out days HURTS on FTMO.** The challenge needs trade frequency to reach +10% in 20
   days; skipping choppy days (B) or all unclear days (D′, −66% of days) starves the target far
   more than it saves losses. The "sit out unclear regimes" pitch — the heart of the 88% claim —
   fights FTMO's target structure. (It would help a firm with a low target / no daily limit,
   where slow steady survival passes — i.e. the 88% likely lives under easier rules.)
2. **Regime *switching* (keep every day, swap legs) is marginally better — on SAFETY, not pass.**
   D lifts test pass only +0.9 (noise) but cuts blow 31%→23%. Same theme as the whole project:
   decorrelation / regime-awareness lowers **blow**, doesn't move the ~55% **mean pass** ceiling.

C's train/test inversion (bad TR, good TE) is regime-luck, not a robust edge; its low blow is
just "fewer days = fewer losses." Threshold quantiles here were computed on all data (mild
look-ahead) — to fix in the next iteration (tune on train only).

## Second cut — the edge-by-regime matrix, OOS-validated (`regime_edge.py`, `router.py`, `sweep_refine.py`)
Instead of guessing, measured each strategy's expectancy **per regime** (prior-day ADX/chop AND
intraday first-hour chop), then OOS-validated every promising cell. What's actually true:

| finding | in-sample | out-of-sample | verdict |
|---|---|---|---|
| **fade (MR) in any regime** | negative everywhere | — | **dead** (the "MR in ranges" pillar doesn't exist on NAS100) |
| **breakout after contraction** (prior-day high chop) | +0.28 / +0.13 | **−0.05** | **noise** — collapsed OOS, rejected |
| **sweep-reclaim on trend-opens** (low 1h chop) | +0.21 | **+0.24** | **REAL** — held OOS, ~2.7× 52p's edge, best single edge in the project |
| momentum after strong-trend days | −0.12 | — | contrarian (breakouts fail post-trend) |

So regime signal is real — but for **sweep/breakout, not fade**, and only the **sweep-on-trend-open**
edge survives OOS. The catch: it fires **~0.33×/day**, so stacking it barely moves a 20-day pass
(52p+sweep: TE 50.8% vs 50.6%). Trying to raise its frequency with more sweep levels (PDH/PDL,
opening-range) **diluted the edge to ~0** (TRAIN −0.07 / TEST +0.08) and *hurt* the stack
(TE→47%). The full switch (52p + sweep + breakout) reaches TE 52.0% / worst-fold 39.8%, but part
of that is the breakout leg that's OOS-noise, so it isn't trustworthy.

## Final honest verdict on the "88%"
- **Regime-switching does NOT reproduce 88% on FTMO.** Done rigorously (train/test + k-fold, OOS
  validation of every cell), it lands at the **same ~55% mean / ~37–40% worst-fold** as 52p.
- **The "sit out unclear regimes" mechanic backfires on FTMO** — the +10% target needs trade
  frequency, so skipping days starves it. That mechanic only pays under easier rulebooks
  (low target / no daily limit / pass-by-survival), which is almost certainly where the 88% lives
  — plus survivorship and a large in-sample tuning surface.
- **One genuine keeper:** sweep-reclaim on directional (low-first-hour-chop) opens, +0.24 expR
  OOS. Real and decorrelated, but low-frequency — so like USDJPY, its value is a few points of
  **worst-fold floor**, not the mean. It cannot be scaled up (frequency dilutes it to noise).
- **Bottom line:** the audited ~55% mean / ~40% floor is the ceiling on NAS100/FTMO. Real edges
  are rare and low-frequency; forcing frequency turns them to noise. An unaudited 88% is not a
  target to chase — it's a number that hasn't met an out-of-sample test.
