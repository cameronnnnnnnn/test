# Topstep 50K Trading Combine — Confirmed Rules (Phase 0)

Status: **awaiting final confirmation on contract choice + subscription cost.**
Everything else below is confirmed by the user (rule #3 confirmed by official Topstep screenshot).

## Account
- Product: **Topstep 50K Trading Combine** (NOT Express Funded — corrected by user).
- Starting balance: **$50,000**.
- Subscription cost: user first said $95/mo (that was for Express); **Combine cost TBC**.
- No Daily Loss Limit on this account.
- No time limit (cost accrues monthly while active).

## Profit target
- **$3,000** → pass when balance reaches **$53,000**.

## Maximum Loss Limit (MLL) — trailing drawdown  [CONFIRMED via official Topstep doc]
- Amount: **$2,000** below the trailing peak.
- Trails off **END-OF-DAY BALANCE** (settled/realized), NOT intraday equity peak.
- Rises as EOD balance grows; **never moves down**.
- **Locks permanently** once it reaches the $50,000 starting balance (i.e., once EOD
  balance has been at least $52,000, MLL = $50,000 forever after).
- Worked example (official):
  - Start: balance $50,000, MLL $48,000.
  - Day 1 +$500 -> EOD balance $50,500 -> MLL trails to $48,500.
  - Day 2 -$500 -> EOD balance $50,000 -> MLL stays $48,500 (never moves down).
- Breach check (to confirm with user): MLL is a hard floor checked **intraday in real time**
  against current equity (open+closed). Hitting it = liquidation + fail. The *level* only
  updates on EOD balance; the *breach* is real-time. Modeling both; default = intraday breach.

## Consistency rule
- Best single day of profit must be <= **50%** of total profit.
- Does NOT blow the account; instead effectively **raises required profit** so that
  best_day <= 50% of total (i.e., must reach total profit >= 2 x best_day, and >= $3,000).
- Dilutable by trading more/smaller days.

## Minimum trading days
- **2**.

## Position limits
- **5 minis (NQ)** / **50 micros (MNQ)**. (Contract choice TBC — recommending MNQ micros.)

## Prohibited / constraints
- **No overnight holds. No weekend holds. Flat by 3:10 PM CT every weekday.**
  - 3:10 PM CT = **23:10 server time** (see timezone note).
  - Violation = risk-desk liquidation + account failure.
- No scaling rules affecting pass.
- No news-trading restriction that constrains the strategy.

## Instrument & data
- Instrument: **NAS100 CFD (ThinkMarkets)** as Nasdaq-100 price proxy.
  - Model fills on futures specs: NQ = $20/point ($5/tick @ 0.25); MNQ = $2/point ($0.50/tick).
- Data file: `data/NAS100_M1_20190101_20260101.csv`, tab-separated,
  columns: DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD.
- **Granularity is mixed**: 2019-01..~2019-08-11 is daily then hourly (NOT usable as M1).
  **True 1-minute data: 2019-08-12 -> 2025-12-31 (~6.4 yrs).** This is the usable set.
- **Timezone**: daily 00:00-00:59 server gap = CME 16:00-17:00 CT break =>
  server = GMT+2 (winter)/GMT+3 (summer), i.e. **CT = server_time - 8h** year-round.
  - RTH (8:30-15:00 CT) = 16:30-23:00 server. Flat-by 15:10 CT = 23:10 server.

## Train/test split
- Train on older ~70%, hold out most-recent ~30% untouched as TEST.
- MC preserves regime clustering (contiguous-calendar / block bootstrap), not i.i.d.
