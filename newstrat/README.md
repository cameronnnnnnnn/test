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

## Next
- Iteration 2: sweep-reclaim + other setup types across all 5 instruments — which carry any edge?
- Then: stack the uncorrelated high-RR edges, MC the 20-day pass vs 52p's ~55%, train/test + k-fold.
