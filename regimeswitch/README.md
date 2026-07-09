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

## Next (open) directions
- Tune regime thresholds on TRAIN only; add expansion (ATR-expansion breakout) and reversal
  (sweep-reclaim) buckets so the switch has a real leg per regime.
- Find a genuinely +EV range-day fade leg (the current fades are weak) — that's what would make
  the switch lift *pass*, not just blow.
- Verdict so far: **no path to 88% mean pass on FTMO yet; regime-switching buys ~8 pts of lower
  blow at ~flat pass.** Consistent with the audited ~55% ceiling.
