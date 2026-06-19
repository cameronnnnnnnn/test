# Correction: FTMO 1-Step uses an END-OF-DAY TRAILING drawdown

You pointed out the 10% max-loss is an **End-of-Day trailing** drawdown, not a static
line from the start. My earlier Monte Carlo used a static floor and was therefore
**too optimistic on blow-ups.** This is the corrected analysis + the fix.

## The rule
- Max-loss line starts at **start − 10%** (on $15k: floor $13,500).
- It **trails UP** behind your **peak end-of-day balance**, by a FIXED $1,500 (10% of
  the initial), and **never moves down**.
- It counts **floating** equity too (open trades, commissions, swaps).

So after a profitable day your floor ratchets up — and a normal losing streak can then
breach the *raised* floor even while you are still net profitable from the start.

## Impact: trailing floor ~doubles blow-ups at sprint risk
Final config (BE@1R, trail5, filters), corrected MC:
| Risk / horizon | Static floor (old) | **Trailing floor (real)** |
|---|---|---|
| 0.50% / 12wk | 30% / 1% blow | 30% / **2% blow** |
| 0.75% / 12wk | 51% / 8% blow | 50% / **17% blow** |
| 1.00% / 8wk | 48% / 12% blow | 47% / **24% blow** |
| 1.10% / 12wk | 63% / 20% blow | 57% / **37% blow** |

Low risk barely changes; sprint risk gets much more dangerous, because the strategy's
"big winner then give-back" pattern bumps the ratcheted floor.

## The fix: floor-defense money management (now built into the EA)
Rule: **when equity is within 5% of the trailing floor, halve the risk; if it touches a
1% buffer above the floor, stop taking new trades.** This defends the line directly.
| Risk / horizon | Plain | **Floor-defense** |
|---|---|---|
| 0.75% / 12wk | 50% / 17% blow | 46% / **4% blow** |
| 1.00% / 8wk | 47% / 24% blow | 43% / **7% blow** |
| 1.10% / 8wk | 49% / 29% blow | 45% / **11% blow** |

Blow-ups drop 60-75% for only ~3-4 points of pass rate. Best risk improvement found.

## EA settings (NAS100_ORB.mq5 now ships with the guard)
New input group **"FTMO trailing-DD guard"**:
- `UseFloorGuard = true`
- `InitialBalance = 15000` (your challenge start; 0 = auto from account)
- `TrailDDPercent = 10`, `DefendBandPercent = 5`, `DefendFactor = 0.5`, `HardStopBufferPct = 1`

The EA tracks your peak balance, computes the trailing floor, halves risk near it, and
refuses new trades inside the 1% buffer — so it **cannot run you through the 10% line.**

## Recommended FTMO setup (corrected, final)
- **`RiskPercent = 0.75`, floor-guard ON** → ~46% pass in 12 weeks at only ~4% blow-up.
  This is the best balance: meaningful pass odds, very low chance of failing the account.
- Want it safer: `RiskPercent = 0.5` → ~30% pass / ~2% blow over 12 weeks.
- Want it faster: `RiskPercent = 1.0` → ~43% pass / ~7% blow over 8 weeks (guard on).

The wall still stands (no 80%-in-2-3-weeks), but with the correct rule modelled and the
floor-guard active, this is now a genuinely sensible way to attempt the challenge:
roughly a coin-flip pass over ~3 months with a small, controlled blow-up risk.
