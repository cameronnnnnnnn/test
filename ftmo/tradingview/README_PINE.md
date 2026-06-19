# NAS100_ORB.pine — TradingView setup

Pine v5 **strategy** (so the Strategy Tester gives you the equity curve directly).

## Load it
1. TradingView → open a **NAS100 / US100 / NDX** chart on a **1-minute** timeframe
   (5-min works but 1-min matches the backtest best).
2. Pine Editor (bottom panel) → paste `NAS100_ORB.pine` → **Add to chart**.
3. Open the **Strategy Tester** tab → see net profit, equity curve, drawdown, trade list.

## Settings that matter
- **Session / timezone:** defaults to `0930-1600` `America/New_York` (US cash open).
  This is broker-independent (uses real NY time), so unlike the MT5 EA you do NOT
  need to figure out a server offset.
- **stopPts = 60** is the 1R stop in index points. Confirm it suits your symbol's scale.
- **riskPct = 1.0** sizes each trade so the 60-pt stop ≈ 1% of equity.
- Range filter + volume confirm are **ON** (the validated config).

## How it differs from the MT5 / Python backtest (read this)
- Pine fills the entry at the **close of the breakout bar** (with volume confirm on
  that bar), vs the backtest entering at the range level. On a 1-min chart the
  difference is tiny, but expect small deviations in exact numbers.
- TradingView free accounts limit intraday history (often ~a few months on 1-min),
  so the sample will be shorter than my 3-year test. Use it to *see the behaviour*,
  not to re-derive the exact +0.169R edge — that needs the full M1 history.
- Greyed background = a day the range filter skipped.

## Want it as an indicator (alerts) instead of a strategy?
Change line 1's `strategy(...)` to `indicator("NAS100 ORB", overlay=true)`, remove the
`strategy.*` calls, and replace entries with `alertcondition(high>=rngHigh and canEnter and volOK, "Long breakout")` etc. The strategy version is better for seeing the equity curve.
