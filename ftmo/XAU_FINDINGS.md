# XAUUSD (Gold) — tested, REJECTED as overfit. Honest writeup.

Gold has the best raw range/spread ratio of anything tested (185:1 at $0.50).
But the data you found is too short and too one-sided to extract a trustworthy
edge, and the apparent edge **fails validation**. I will not build on it. Here is why.

## Data (real, user-supplied M1)
- 188,702 one-minute bars, 99.9% clean.
- **Range: 2025-11-24 → 2026-06-18 = 6.8 months only** (NAS100 had 36 months).
- Price **$4,024 → $5,593 = +40% in 7 months** — an extreme, one-directional bull run.
- 148 trading days. That is a *tiny* sample for strategy validation.

## What we found, and why it is not real
Intraday ORB scan: most session hours **lose** (−0.06 to −0.26R). One hour looked
great — 13h server: +0.206R, both sides positive, n=144. We stress-tested it:

| Test | Result | Verdict |
|---|---|---|
| Cost stress $0.4→$1.5 | stays positive | ok |
| Stop-size sweep | stable | ok |
| **Neighbouring hours** | 11h −0.30, 12h −0.36, **13h +0.21**, 14h −0.07 | **FAIL** — edge exists only at one exact hour, negative on both sides of it |
| **Walk-forward (split in half)** | 1st half +0.04R (short side −0.16), 2nd half +0.37R | **FAIL** — all the edge is in the last 3 months |

A real session edge bleeds into neighbouring hours and shows up in **both** halves
of the sample. This one spikes at a single isolated hour and lives entirely in the
final 3 months of a +40% melt-up. That is the signature of **noise mined from a
short, regime-skewed sample** — not a durable edge.

## Decision
- **Rejected.** Presenting a Monte Carlo pass-rate off this would be curve-fitting
  a number you explicitly told me not to produce. The honest call is to throw it out.
- **NAS100 remains the only validated strategy** (3-yr sample, walk-forward held
  in-sample +0.131R / out-of-sample +0.124R, both sides positive across the *whole*
  sample, edge present in every sub-period).

## What WOULD make gold usable
Gold's range/spread is genuinely superior to NAS100, so it could yield an even
better edge **if** validated properly. To do that I need:
- **2–3+ years of XAUUSD M1** (covering 2021–2023: gold's chop, the 2022 selloff,
  range-bound periods — not just the 2025–26 bull run), so I can walk-forward across
  different regimes and confirm both long and short sides hold.
With that, gold is the most promising instrument tested. With only 7 bull-run
months, it cannot be trusted.

## Bottom line
More range/spread does not help if the sample can't prove the edge is real.
Gold = best raw material, worst sample. Get longer history and it goes back on the
table; until then, **NAS100 ORB is the strategy.**
