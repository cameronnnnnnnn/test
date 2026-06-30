# challengephasev2 — feature-engineered challenge-pass research

Goal set by the loop: build a NAS100 FTMO 1-Step ($15k) challenge strategy via the
"quant process" feature-engineering methodology and **loop features → strategies →
backtest → improve** until it hits **80% pass in ~20 trading days**, respecting all
FTMO rules (+10% target, 10% static floor, 3% daily loss, 50% consistency, min 4 days).

This README is the honest lab notebook. **Headline result up front: 80% pass in 20
days is not attainable on NAS100 under FTMO 1-Step rules with honest, out-of-sample
edges.** The rigorous ceiling is ~44% in 20 days (~66% even if you allow 90 days).
The reasons are structural and are documented below with numbers. The best *honest*
strategy the loop produced is in "Deliverable" at the bottom.

## Files
- `features.py`  — look-ahead-free bar-level feature library (18 features): candle
  geometry/wicks, daily ATR + volatility regime, session-VWAP distance & slope,
  ATR-normalised momentum (5/15/30), realised vol, time-of-day, day-of-week. Plus
  4 **event-defining** generators: ORB break, prior-session **sweep**, **CUSUM**
  movement-burst, prior-day H/L break.
- `signal_lab.py` — labels each event with a double-barrier (±1R) outcome via the
  engine, attaches contextual features at the signal bar, and measures conditional
  win-rate/expectancy **TRAIN (70%) vs TEST (30%)** so only out-of-sample edges count.
- `strat_gen.py`  — turns surviving contexts into strategies + risk geometry and
  reports the real FTMO 20-day pass rate, TRAIN vs TEST (reuses `ftmo.run_mc`).
- `iter2_probe.py` — filtered entries + runner exits (drift geometry).
- `iter3_probe.py` — daily circuit breaker + deadline-sensitivity sweep.

All reuse the bug-fixed `ftmo/v4` engine, strategy library, data loader and FTMO MC.

## Iteration log

### Iter 1 — feature engineering & signal lab (`signal_lab.py`)
Base events are near-coinflips at the trade level (double-barrier ±1R, cost-adjusted):
ORB 50.2% WR, sweep 48.4%, CUSUM 51.0%, PDHL 50.3%. Contextual filtering, validated
out-of-sample, lifts the best buckets only modestly:
- **CUSUM (momentum burst) is the standout** — many contexts survive OOS to 56–68%
  test WR (with-trend VWAP slope, follow-through momentum, mid-session, normal vol).
- ORB / sweep / PDHL: most "edges" are train-only and **flip negative on test**
  (textbook overfit). Only weak survivors (e.g. ORB after the first ~25 min).

### Iter 2 — geometry (`strat_gen.py`, `iter2_probe.py`)
- **High-WR / low-RR (the convex prop-firm geometry) TIMES OUT.** CUSUM-with-trend at
  tp 0.5–0.75R reaches 61–70% WR with +EV, but passes **0–7%** in 20 days: it almost
  never reaches +10%. Its drift (edge × ~0.3 trades/day × risk) is ~0.02%/day — that
  geometry needs *hundreds* of days to make 10%. **It is a funded-phase tool, not a
  challenge tool.**
- **Runner / high-RR geometry** (filtered entries + 4–6R / trail) restores drift.
  Single filtered setups have excellent trade quality (expR +0.10…+0.16, PF 1.16–1.35)
  but too few signals → timeout. Merging 3 decorrelated setups for frequency gives
  ~36–43% test pass but 40–53% blow (the 3% daily cap bites).

### Iter 3 — the two remaining levers (`iter3_probe.py`)
- **Daily circuit breaker** (stop the day after −2R) is a genuine win: cuts blow
  40.7%→27.7% and lifts test pass 37.5%→**43.2%**, and drops the share of blows caused
  by the 3% daily cap from 49%→18% (much more robust failure mode). A −1R breaker at
  slightly higher risk → 44.9%.
- **Deadline sensitivity** (runner combo, −2R breaker): 20d→43%, 30d→52%, 40d→56%,
  60d→59%, 90d→66%. The 20-day ceiling is ~44%; you'd need ~90 days to reach ~66%,
  and **never 80%**.

## Why 80%/20d is structurally impossible here (the honest conclusion)
1. NAS100 intraday events are near-coinflips; the best honest OOS filter buys ~5–10
   WR points, not 30.
2. To hit **+10% in 20 days** you need positive-skew **drift** — but the **drift that
   reaches the target fast also creates the variance that, under the 3% daily cap +
   10% floor, blows 28–50% of attempts.** Speed and survival trade off against each
   other; the frontier tops out near ~44% in 20 days.
3. The low-variance, high-WR geometry that *would* push pass rate up has too little
   drift to reach the target in time — it just times out.
4. The video's 80–90% pass was on **TOPSTEP, which has no daily loss limit** (and a
   trailing drawdown). Remove FTMO's 3% daily cliff and the high-WR geometry stops
   blowing — but FTMO has it, so the geometry that wins on Topstep loses here. The
   rule set, not the signal, is the binding constraint.

Pushing past ~44% in-sample is achievable only by overfitting (the train-only 60% WR
buckets that collapse to ~40% on test) — i.e. a mirage that fails live. The loop is
therefore stopped honestly rather than fabricating an 80% number.

## Deliverable — best honest challenge strategy
**CUSUM-with-trend (stop 50, 6R, BE@1R) + filtered ORB (stop 50, 6R, BE@1R) +
VWAP-pullback (stop 40, 6R) + a −2R daily circuit breaker, ~1.0% risk.**
Out-of-sample: **~43% pass / ~28% blow / ~29% timeout in 20 days, median 10 days.**
This matches the live baseline's pass rate but with a materially safer failure mode
(daily-cap blow share 18% vs ~49%) and a genuine feature-edge leg (CUSUM continuation).

It does **not** reach 80%. Given the ~44% structural ceiling, the right way to "profit
from the challenge" is the **convex multi-account EV** already validated in
`ftmo/v4/funded_pipeline.py`: each $135 challenge is +EV because the downside is capped
at the fee and a pass is worth a funded account. Higher per-account pass is only bought
with *time* (the 40–90 day paths above), not with a cleverer 20-day signal.
