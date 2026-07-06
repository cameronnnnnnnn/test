# Topstep 50K Combine on NAS100 — Final Report (brutally honest)

**Bottom line up front:** On this instrument and dataset, under the confirmed
Topstep rules and the hard **flat-by-3:10-PM-CT (no overnight)** constraint,
**there is no robust, causal, cost-surviving intraday edge.** The honest
achievable pass rate per attempt is **~20–35%, and it is driven by low-risk +
trailing-stop geometry, NOT skill.** Every strategy I built matched a
**zero-edge random control**, and the configs that looked best in-sample
reversed out-of-sample. I will not curve-fit a bigger number. Details below.

---

## 1. What was confirmed (Phase 0)
- Product: **Topstep 50K Trading Combine**, $50k start, target **+$3,000** (pass at $53k).
- **Max Loss Limit: $2,000 trailing off END-OF-DAY balance**, never down, **locks
  permanently at $50,000** once EOD balance reaches $52,000. (Official screenshot.)
  Breach is checked **intraday** in real time against live equity.
- No daily loss limit. Min **2** trading days. **No time limit** (cost $49/mo).
- **Consistency:** best single day ≤ 50% of total profit (gates the pass; dilutable).
- Position cap: 5 NQ / 50 MNQ. We sized in **MNQ micros** ($2/pt) for fine risk control.
- **No overnight / no weekend. Flat by 3:10 PM CT every day.**

## 2. Data (Phase 1)
- File: `NAS100_M1_20190101_20260101.csv` (ThinkMarkets NAS100 CFD, tab-separated).
- **Granularity is mixed**: usable true 1-minute data is **2019-08-13 → 2025-12-31
  (6.38 yrs, 1,989 days)**. Earlier rows are daily/hourly and were discarded.
- **Timezone solved from the data**: the daily maintenance gap sits exactly in the
  server 00:00 hour = CME 16:00–17:00 CT break ⇒ **CT = server − 8h**. Validated:
  after conversion the break lands at 16:00 CT and RTH averages **384.6/390 bars/day**.
- Split: **TRAIN = oldest 70%** (to 2024-02-01), **TEST = newest 30%** (untouched
  until final validation).

## 3. Simulator (validated)
`src/simulator.py` encodes the rules exactly (EOD-balance trailing, lock-at-start,
intraday breach, consistency gate, min-days) and **passes 4 hand-worked cases**
(clean pass, consistency-blocked pass, intraday breach on a positive-close day,
and the lock-cap surviving a dip that would otherwise breach). Monte Carlo uses
**contiguous-calendar** sampling (a real challenge is one contiguous stretch) plus
**block-bootstrap**, both preserving regime clustering. 10,000 paths per test.

## 4. The evidence that there is no edge

### 4a. Zero-edge control — the key benchmark
A mean-**zero** gaussian daily P&L (no skill whatsoever) under these exact rules:

| daily vol | H=250 pass% | blow% | median days |
|-----------|-------------|-------|-------------|
| $150      | 20.4%       | 63.6% | 172         |
| $250      | **29.6%**   | 69.5% | 69          |
| $400      | 23.8%       | 76.0% | 28          |

**A coin flip passes ~20–30%.** This is pure geometry: a $3,000 target against a
$2,000 trailing stop caps a driftless process near ~30%. **Any strategy that only
reaches ~30% has demonstrated no skill.**

### 4b. Every strategy matched the control
Best out-of-sample pass rates across families (ORB, trend-session long/short,
long-only strong-trend, late-session) landed at **~15–35%** — i.e. on top of the
zero-edge line, not above it.

### 4c. The per-day edge CI includes zero — everywhere
Bootstrap 95% CI of mean daily P&L (qty=1), TrendSession both/sma50/stop40, by year:

| year | mean/day | 95% CI | significant? |
|------|----------|--------|--------------|
| 2019 | +$2.53 | (−14.6, +25.3) | no |
| 2020 | −$6.26 | (−23.7, +10.9) | no |
| 2021 | −$1.23 | (−19.6, +17.0) | no |
| 2022 | +$14.64| (−13.1, +42.6) | no |
| 2023 | +$12.00| (−8.6, +35.4) | no |
| 2024 | +$4.91 | (−16.1, +27.2) | no |
| 2025 | +$11.43| (−14.0, +39.4) | no |

No year is significant, and the **sign flips** across years. The intraday drift is
real but regime-dependent and washes out once you require causality and pay costs.
Late-session (13:30 CT) entries — the strongest signal in reconnaissance — also
had a TRAIN edge CI including zero.

### 4d. In-sample winners reverse out-of-sample (overfitting proof)
Long-only strong-trend (sma100), defined target:

| config | TRAIN mean/day | TRAIN qty3 pass | TEST mean/day | TEST qty3 pass |
|--------|----------------|-----------------|---------------|-----------------|
| stop25/tgt40 | +$1.92 | **42.9%** | **−$6.90 (CI excl 0!)** | **0.0%** |
| stop30/tgt30 | +$1.37 | 28.7% | −$8.93 (CI excl 0) | 0.0% |

The best in-sample number (42.9%) is a **mirage** — the identical rule loses money
with statistical significance on unseen data.

## 5. Risk-vs-time frontier (the biggest lever, explored)
Because daily P&L scales linearly with contracts, I swept qty on the trend family.
Lowering per-trade risk **does** cut blow-up and, with no time limit, nudges pass%
up — but it plateaus at the zero-edge ceiling and stretches median days-to-pass to
**75–230 days** (2.5–8 months of $49 subscriptions). Example (TEST, both/stop40):

| qty | $risk/day | pass% (H=250) | blow% | median days |
|-----|-----------|---------------|-------|-------------|
| 1   | ~130      | 29.9%         | 60.9% | 75          |
| 3   | ~400      | 29.9%         | 64.6% | 24          |
| 5   | ~660      | 15.1%         | 81.8% | 12          |

More size = faster but far more blow-up; less size = safer but slow, and never
escapes ~30%. This is the frontier of a **no-edge** process.

## 6. Why (economic rationale)
The one drift that is reliably positive on the Nasdaq is the **overnight** move
(recon: overnight sum ≈ intraday sum, and equity indices historically drift most
outside RTH). Topstep's **no-overnight rule bars us from harvesting it.** The
tradeable RTH drift is smaller, regime-dependent (strongly negative in 2022), and
not separable from noise net of costs. That is a structural limit, not a tuning
failure.

## 7. Honest achievable outcome
- **Pass probability per attempt: ~25–30%**, essentially the zero-edge ceiling.
- **This is a LOW-RUIN pass, not a STRONG-EDGE pass** — the per-trade edge CI does
  not exclude zero in-sample or out-of-sample.
- Expected attempts to pass ≈ 1/0.30 ≈ **3.3 resets ⇒ ~$160+ in fees**, and each
  successful attempt would then face the **same ~30% odds every payout cycle** in a
  funded account, because the underlying process has no edge. Passing once ≠ a
  sustainable income; it would be luck.
- **Recommended sizing if you attempt anyway:** smallest size that still reaches
  target in reasonable time — **~2–3 MNQ, ~25–40 pt stop, trend-filtered direction,
  flat by close.** This maximizes the low-ruin pass odds (~30%) and minimizes the
  chance of a Phase-1 ($50k→$52k) trailing-stop-out. Do **not** scale up chasing
  speed; it only raises blow-up.

## 8. Caveats
- CFD data (not NQ futures): spread/financing differ; I modeled MNQ futures specs +
  ~$2/contract round-turn cost (commission + 1 tick/side slippage). Real slippage on
  stops in fast markets could be worse, lowering pass% further.
- I did **not** exploit overnight drift (rule-barred). If you can find a *different*
  instrument/rule set that permits overnight holds, the analysis changes entirely.
- I stopped searching once the zero-edge control, all-years-insignificant CIs, and
  the OOS reversal converged — continued mining of the (now-seen) TEST set would be
  overfitting, which the brief explicitly forbids.

## 9. Reproduce
```
python3 src/load_data.py       # clean data -> data/clean_m1_ct.parquet
python3 src/simulator.py       # validate rules engine (hand-worked cases)
python3 src/explore.py         # edge reconnaissance (TRAIN)
python3 src/run_experiment.py  # ORB baseline (logs results/iterations.jsonl)
python3 src/loop1.py           # trend-session sweep
python3 src/loop2.py           # risk-vs-time frontier
python3 src/loop3.py           # zero-edge control + per-year CI + OOS reversal
```
All iterations are logged to `results/iterations.jsonl`.
