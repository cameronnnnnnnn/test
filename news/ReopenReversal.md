# The 6pm Reopen Reversal — full spec

**Edge:** the CME reopen (6:00pm ET) after the 5–6pm halt prints into a thin book; the first
minute's move overshoots and mean-reverts. Fade it. Backtest: 707 nights (2022-10 → 2025-10,
NAS100 M1, 1.5pt cost): grind +0.118R/night, sprint +0.160R/night; positive in 3 of 4 time folds
(flat in the 2022 bear); the reversal works at NO other session open (verified against Tokyo,
London, midnight ET, 8:30, 9:30 — all negative), which is what ties the edge to the halt.

## The rule (every night)
1. **6:00pm ET** — market reopens. Watch the 6:00–6:01 1-minute candle.
2. **Gap filter:** reopen gap (6:00 open vs 4:59pm close) > **100pts** in either direction →
   **no trade tonight** (n=14 such nights historically: 29% WR, −0.12R — news, not noise).
3. **At 6:01pm close:** candle **green** (closed above *its own* 6:00 open) → **SELL**;
   **red** (closed below its own open) → **BUY**; doji → no trade.
   *The candle's own open — NOT yesterday's close. The gap direction is irrelevant (tested: all
   gap rules lose).*
4. **Enter market at 6:01pm.** One trade per night. No management: no breakeven, no trailing,
   no partials (intraday-trailing accounts punish runners — trail exits were worst in every cell).
5. Stops/targets (Apex intraday-trail):
   * **50K: SL 40pt / TP 120pt (3R)**
   * **100K: SL 50pt / TP 125pt (2.5R)** (closer TP banks before the intraday trail ratchets)

## Two exit configs
| | **GRIND** (max pass rate) | **SPRINT** (max speed) |
|---|---|---|
| exit | flat **2:55am ET** if no TP/SL | hold to TP/SL; force-flat 4:55pm ET |
| WR / expR | 46.8% / +0.118R | 30.6% (69% full-SL) / +0.160R |
| TP-hit rate | 8% (56% exit EOD at +0.47R avg) | 29% |
| Apex 50K @$500 | pass 41% · med 13n · P≤5n 5% | pass 29% · **med 5n · P≤5n 16%** |
| blow | 59% | 71% |

## Sizing (per night, fixed $)
* Apex 50K: **$400–500 = 5–6 MNQ micros** ($80/micro at 40pt). Never above ~$560.
* Apex 100K: $400–560 = 4–5.5 micros ($100/micro at 50pt). (100K is poor value — prefer two 50Ks.)
* Worst night is exactly −1R by construction, so daily-loss limits can't breach at these sizes.

## Fleet plan (10+ accounts)
* Mix **grind and sprint accounts** — different exits genuinely decorrelate (same night can win
  on grind and lose on sprint), unlike risk-laddering alone.
* **Stagger start dates** 1–2 weeks so trailing-DD paths differ.
* Do NOT flip direction on any account (the anti-side is −EV).

## Never
* Trade the candle's direction (continuation is −0.22R, t=−5.3 — the one *proven* thing).
* Apply this at any other open. * Run winners / trail on intraday-trail accounts.
* Trade a >100pt-gap night. * Compare the candle to yesterday's close.

## Caveats (honest)
* Regime: the 2022 bear fold was ~0EV — expect the edge to flatten in sustained bear regimes.
* Sprint's 69% full-loss rate = long losing streaks (5+ straight is common); size for it.
* A 5-trade manual sample proves nothing (a 5-night sprint pass is a ~16% shot); plan on the MC
  numbers. Verify your platform's 6:01pm ET fill quality/spread before sizing up.
