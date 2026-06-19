# NAS100 (US100) — the better instrument, tested. Findings.

You were right to switch instruments. NAS100 is **dramatically** better than the FX
majors for this task. But the 2–3 week, ≥80%, ≤3%-daily target is **still not
reachable** — here is the full, honest picture with real data.

## Data (real, user-supplied MT5 M1)
- 1,042,353 one-minute bars, **2022-10-18 → 2025-10-01 (~3.0 years)**
- 99.9% clean 1-minute spacing, 24h coverage, no spread column (used conservative 2pt cost, stress-tested to 6pt)
- Price 10,629 → 24,811 (one large bull run — so every result below is checked long-vs-short and walk-forward)

## Why NAS100 beats EURUSD/GBPUSD
| Metric | EURUSD | NAS100 |
|---|---|---|
| Daily range / spread ratio | 63:1 | **131:1** (2pt) |
| Fat tail (99th pct ÷ median range) | ~2× | **3.5×** (934 vs 263 pts) |
| Best intraday edge after real cost | negative | **+0.128R** |
| Trades/week with edge | ~2 (daily only) | **5** (intraday) |
| Biggest single winner in sample | ~4R | **8–38R** (per config) |

Intraday worked here because the range/spread ratio is double — the spread that
killed every FX intraday edge is negligible against a 250–900pt NAS day.

## The strategy (locked, legitimate, validated)
**NAS100 opening-range breakout, US cash session.**
- Server 16:00 (US cash open — located from tick-volume peak), build the first 30-min range.
- Break of range high → long; break of low → short. Fill at the break (real M1).
- Fixed **60-point stop**; trail the stop at **3R** once in profit; **flat by end of day**.
- No Friday entries, no weekend hold. **One trade/day** → daily risk is a clean 1R.

**Edge:** expR **+0.128**, win 35.6%, PF 1.21, ~5 trades/week.
**Honesty checks (all pass):**
- Walk-forward: in-sample +0.131R, **out-of-sample +0.124R** (2024-07→2025-09, includes the Aug-24 and early-25 selloffs). Edge holds.
- Long +0.161R **and** short +0.093R — both sides positive, not just bull beta.
- Cost stress 2→6pt: edge survives.

## FTMO Monte Carlo (all 5 rules: 3% daily, 10% overall, 10% target, consistency, min days)
Pass% / Blow-up% by deadline:
| Deadline | r=1.0% (safe) | r=1.5% | r=2.0% (aggressive) |
|---|---|---|---|
| 2 weeks | 9.5% / 0.4% | 18.5% / 9.2% | 24.5% / 21.6% |
| 3 weeks | 17.9% / 4.2% | 31.4% / 17.8% | 37.5% / 31.2% |
| 4 weeks | 25.5% / 7.6% | 39.2% / 23.6% | 44.8% / 36.7% |
| 6 weeks | 37.2% / 14.6% | 49.3% / 31.4% | 51.2% / 42.2% |
| 8 weeks | 45.6% / 18.8% | 54.7% / 34.8% | 53.3% / 44.3% |
| 12 weeks | 56.1% / 25.0% | 58.9% / 38.4% | — |
| unlimited | **68.4% / 31.6%** | 60.5% / 39.5% | 54.5% / 45.5% |

## Verdict
- **2–3 weeks at ≥80%: still impossible.** Best 3-week pass is ~37%, and only by
  risking 2%/trade — which blows up 31% of the time. The pass rate **ceilings at
  ~68% at any deadline**, never 80%.
- **Why the ceiling:** the 10% overall-drawdown limit vs a 36%-win-rate strategy.
  ~30% of runs hit a losing streak that breaches drawdown before reaching +10%.
  You cannot push blow-ups below ~30% without cutting risk so far you time out.
- **But this is a genuinely fundable strategy** — 20× better than anything FX offered.
  Realistic plan: **r = 1.0–1.5%, expect to pass ~45–55% of attempts over 6–8 weeks**
  with a controlled (~15–30%) blow-up rate.

## Bottom line
The instrument switch was the right call and got us from ~2% to ~37% in three weeks.
The remaining gap to 80%-in-2-weeks is not a strategy problem — it is the arithmetic
of a 10% drawdown cap and a thin (if real) edge. Speed (high variance) and 80%
reliability (low variance) cannot both hold. The honest max is: a real edge, run
patiently at low risk, ~half of attempts succeed over roughly two months.
