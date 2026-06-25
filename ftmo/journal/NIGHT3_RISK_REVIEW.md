# Night-3 risk review — the live account after the 6-for-6 cold start

_Generated 2026-06-25, after 3 trading nights (6 trades). Companion to the auto
`debrief`; this one answers "given where we actually are, what now?"_

## Where the account is (hard numbers)
| | |
|---|---|
| Balance / equity (flat) | **$14,249.73** (−5.00%) |
| Static fail floor (10%) | $13,500.00 |
| **Cushion to permanent fail** | **$749.73 ≈ 4.0R** |
| Distance to +10% target | $2,250.27 |
| Trades | 6 (sessions 15 & 16 × 3 nights) |
| Win rate / expectancy | **0% / −0.68R** |
| Winning days banked | **0** |

Per-trade ledger: 4 full stops (−1.0 to −1.04R) + 2 breakevens (ORB15 nights 1–2,
the BE@1R move saved them). **All 6 were longs.**

## Three things the data actually says

### 1. The cold streak is (barely) within variance — but the regime isn't friendly
At WR ≈ 31%, six non-wins in a row is ≈ `0.69^6 ≈ 11%` — uncomfortable, not alarming,
and two of the six were breakevens, not losses. **But all six were long breakouts that
got faded while NAS sold off ~1,100 pts (30,512 → 29,402) across the three nights.**
The EA is both-sided (`LongOnly=false`, it just checks the up-break first); the tape
simply broke range-*highs* first every session and reversed — a textbook "sell-the-rip"
regime. The documented edge leans partly on NAS up-drift (long +0.16R vs short +0.09R),
and that tailwind is currently absent. This is regime drag on top of normal variance,
**not** evidence the strategy is broken.

> Do **not** flip the EA to `LongOnly=true` here. That mode is a bet on up-drift; in a
> down-tape it would have taken the same six losing longs and skipped any shorts. Wrong
> direction for the current regime.

### 2. The cold start has roughly DOUBLED the odds of busting
Conditional Monte-Carlo from the *current* $14,249.73 with 0 wins banked
(`mc_conditional_ruin.py`, edge calibrated to the documented expR +0.128 / WR 31% /
PF 1.21, static $13,500 floor, 3% daily cap, EA-style balance-scaled 1R):

| State | pass | blow-up |
|---|---|---|
| **Fresh $15k** @1.25%, 2 sess (unconditional) | ~65% | ~35% |
| **Now ($14,250, 0 wins)** @1.25%, 2 sess | **~40%** | **~60%** |
| Now, with realistic clustered bad days (ρ=0.5) | ~37% | **~63%** |

The 5% hole flipped the account from ~65/35 *for* us to ~40/60 *against*. That is the
dominant fact tonight: **from here it is more likely to fail than to pass.** (Sanity
check: the "fresh" row reproduces `NAS100_FINDINGS.md`'s published r=1.25% line, so the
model is trustworthy.)

### 3. Two sessions/day is what spent the floor this fast — and it barely helps
The validated playbook is **one trade/day** ("daily risk is a clean 1R … the 3% rule is
essentially never binding"). The live EA runs **`SessionHours="15,16"` = two**. Effect:

- **Daily-cap headroom is thin but intact at 1.25%.** A double-full-loss day costs
  ≈ −2.48% (−2.58% at the slippage we actually got, ~−1.04R/stop), vs the −3.00% cap —
  i.e. only ~$60–75 of room. Safe by a hair, but it means **you can never size up to
  1.5%** (two losses there ≈ −2.98% = instant daily fail).
- **It does not improve terminal odds.** At a long horizon, 2-vs-1 session is a wash on
  pass/blow-up (~40/60 either way); it only resolves *faster*. Under realistic
  day-clustering it is slightly *worse* (63% vs 60% blow-up). The real cost already
  happened: two sessions burned through 5% of the 10% floor in three nights.

## Recommendation (survival-first)
The edge is real and this is a fundable strategy — but conditional on a 4R cushion the
maths is now a coin-flip *against*, and risk reduction has limited power this close to
the floor (the damage is mostly done). Play for survival, not for a fast pass:

1. **Cut risk to 1.00%/trade.** Best conditional balance in the table (≈44% pass /
   ≈56% blow-up at 24wk, and it lowers the 8-week blow-up 58%→52% for ~no pass loss).
   At 1.0%, a double-loss day is ≈ −2.0% — comfortable daily-cap margin restored.
2. **Keep the validated, both-sided config. Do not enable `LongOnly`.** The losing run
   is regime + variance, not a fixable signal bug.
3. **Optional: drop to one session (16:00, the validated open).** Doesn't change
   terminal odds but halves the daily bleed-rate and the variance — sensible while
   nursing a thin cushion. The live 3-for-3 loss on session 16 is noise (n=3); 16:00 is
   the backtest's strongest session, so keep it if you keep only one.
4. **Bank a green day before anything else.** Consistency/best-day rule is irrelevant
   until there's profit to spread; the 3R hard TP already handles it.
5. **Know the off-ramp.** If the cushion reaches ~2R (~$13,875) with still no winning
   day, you're in the ~70%+ blow-up tail — a fresh challenge ($100, refunded on first
   payout) is the better EV than forcing the last 2R.

_Reproduce: `python3 ftmo/mc_conditional_ruin.py`._
