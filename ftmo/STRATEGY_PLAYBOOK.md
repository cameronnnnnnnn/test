# NAS100 ORB — Optimized Strategy Playbook (final)

After testing breakeven stops, trailing aggression, daily-bias filters, target caps,
and a NAS100+Gold combo — all through the full FTMO-rule Monte Carlo — here is the
best legitimate strategy and the exact dials. Bottom line up front: the optimizations
**improve the risk-adjusted profile** (higher PF, ~25% fewer blow-ups) but do **not**
break the 80%-in-2-3-weeks wall. That wall is the edge size vs the 10% drawdown cap.

## What the optimization found
| Lever | Verdict |
|---|---|
| **Breakeven stop @ 1R** | **KEEP** — raises PF 1.21→1.26, cuts blow-up ~25% for ~no pass loss |
| Trail tightness (1.5R/2R/3R) | **3R = most pass; 1.5R = safest.** Your risk dial. |
| Breakeven earlier (0.5R) | worse — chokes winners (expR 0.129→0.109) |
| Daily-bias filter (trade only with 20d trend) | **HURTS** — removes good counter-trend session breakouts |
| Target cap (5R) | neutral — skip it, trailing does the job |
| **Add Gold (10y or 22y)** | **HURTS** — gold has no edge; diluting NAS lowers pass rate |

## The strategy (config B — recommended)
**Instrument:** NAS100 (US100). **One trade per day.**
1. At **server 16:00** (US cash open — the high-volume hour), mark the **first 30-min
   range** (high = RH, low = RL).
2. **Long** if price breaks RH; **short** if price breaks RL. Enter at the break (first
   touch). Take the first breakout only — no re-entry.
3. **Stop = 60 points** from entry (this is your 1R).
4. **Breakeven:** once the trade is **+1R** in your favour, move stop to entry.
5. **Trail:** ratchet the stop to **3R behind the running extreme** (loose — lets fat
   tails run; tighten to 1.5R if you want fewer blow-ups).
6. **Exit** the remainder at **end of day** (server 23:00). **Flat overnight, flat
   weekends.** No Friday-into-Monday holds.

**Edge (3yr real M1, walk-forward validated):** expR **+0.129**, PF 1.26, win 27%,
~5 trades/week, maxR 8.3. Long +0.16R and short +0.09R both positive. Holds
in-sample (+0.131R) and out-of-sample (+0.124R).

## Risk menu (config B, FTMO $15k, all 5 rules enforced)
Pass% / Blow-up% by deadline and per-trade risk:
| Deadline | r=1.0% | r=1.25% | r=1.5% | r=2.0% |
|---|---|---|---|---|
| 2 weeks | 7% / 0% | 11% / 2% | 14% / 5% | 19% / 17% |
| 3 weeks | 15% / 2% | 22% / 6% | 26% / 13% | 33% / 25% |
| 4 weeks | 23% / 5% | 31% / 11% | 35% / 18% | 41% / 31% |
| 6 weeks | 35% / 10% | 43% / 18% | 48% / 26% | 51% / 38% |
| 8 weeks | 44% / 14% | 51% / 22% | 54% / 31% | 54% / 41% |
| 12 weeks | 56% / 20% | 60% / 28% | 60% / 35% | 56% / 43% |
| 24 weeks | 69% / 26% | 67% / 32% | 63% / 37% | 56% / 44% |

**Daily-loss safety:** one trade/day with a 60pt stop = max 1R loss/day. At r≤2% that
is ≤2% < the 3% daily cap, with margin. The 3% rule is essentially never the binding
constraint — the 10% overall drawdown is.

## How to use it
- **Want best odds, patient:** r = 1.0–1.25%, give it 8–12 weeks → ~50–60% pass,
  blow-up ~14–28%. This is the sane way to run it.
- **Want a fast sprint:** r = 1.5–2%, 3–4 weeks → ~26–41% pass, but blow-up 13–31%.
  It is a gamble; size it as money you can lose.
- **Tighten trail to 1.5R** if minimising blow-up matters more than max pass.

## The honest verdict (unchanged, now optimized)
- The pass rate **ceilings around 68–69%** at any deadline. **It never reaches 80%**,
  and **2–3 weeks at 80% remains impossible** — proven across EURUSD/GBPUSD (no real
  edge), Gold (22y, no edge), and NAS100 (real edge, but thin vs a 10% drawdown cap).
- The optimizations were worth doing: breakeven@1R is a genuine free improvement, and
  you now have a tuned risk dial. But they refine the odds, they do not rewrite the math.
- **This is a real, fundable, fully-validated strategy.** Run it patiently at low risk
  and it passes roughly half to two-thirds of attempts over 1.5–3 months. That is the
  honest best a legitimate FX/index/gold edge can do under these rules.
