# NAS100_ORB.mq5 — setup & testing

The EA implements the validated config **B**: US-session opening-range breakout,
60-pt stop = 1R, breakeven at +1R, trail 3R behind the extreme, one trade/day,
flat by end of day, no Friday entries.

## Install
1. MT5 → File → **Open Data Folder** → `MQL5/Experts/` → copy `NAS100_ORB.mq5` there.
2. MT5 → **MetaEditor** → open the file → **Compile** (F7). Should be 0 errors.
3. Restart MT5; the EA appears under Navigator → Expert Advisors.

## CRITICAL: verify two things before trusting results
1. **Server time of the US cash open.** The strategy keys off **server 16:00** in my
   data. *Your* broker's server may differ (UTC offset). Find your broker's server
   time, work out when 09:30 New York is in server time, and set `SessionOpenHour`
   accordingly (it is usually 15, 16 or 17). Wrong hour = wrong strategy.
2. **`StopDistance` units.** It is in **price/index points** (e.g. 60.0 means the SL is
   60.0 away from entry on a price like 24585.7). Confirm 60 points ≈ your intended 1R.

## Backtest in Strategy Tester
- Symbol: your broker's NAS100 / US100 (cash CFD).
- Timeframe: M1 (the EA reads M1 internally; tester model "Every tick based on real ticks" is best).
- Period: as much history as your broker provides.
- Inputs: `RiskPercent=1.0`, `StopDistance=60`, `BreakevenR=1.0`, `TrailR=3.0`.

## Expected behaviour (from my 3y研究 / research)
~5 trades/week, win ~27%, profit factor ~1.26, occasional large (5–8R) winners.
It will have many small losing days and a few big winners — that is the design.
Do NOT judge it on a handful of trades; it needs dozens to express the edge.

## FTMO safety
One position at a time with a hard stop ⇒ worst single-day loss ≈ 1R. At
`RiskPercent ≤ 2` that is ≤ ~2%, inside the 3% daily cap. The binding risk is the
10% overall drawdown — keep `RiskPercent` at 1.0–1.5 to stay well clear.
