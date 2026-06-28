# FTMO funded-phase — optimized for net banked $/month (iteration 7)

Objective: maximize **expected real banked dollars per month** = E[Σ your-90% withdrawals
over the account's life] ÷ lifetime, **net of amortized re-acquisition cost**. Convex-EV
principle: banked cash is permanent, the account's downside is capped at its cost, so we
optimize banked $ (not survival/win-rate) and front-load withdrawals.

Rules modeled (confirmed): $15,000 · 90/10 · static $13,500 floor (10%, no trail) · 3%
($450) intraday daily loss · payout cadence choosable 14/30/60d · min $20 / no max ·
**50% best-day consistency rule** (blocks payouts until best winning day ≤ 50% of total
winning-day profit — doesn't fail the account).

## The winner (iteration 7)

**Strategy (3 setups/day):**
- **US-open ORB** — 16:00 server (~09:00 ET), 30-min range, 60pt stop, **6R TP**, vol-confirmed, **BE after +1R**
- **EU-open ORB** — 11:00 server (~04:00 ET), 30-min range, 60pt stop, **6R TP**, vol-confirmed, **BE after +1R**
- **VWAP trend pullback** (US session) — 40pt stop, **8R TP**, **3R trailing stop**

**Risk:** ~**$100/trade** (≈0.67% of $15k; 3 setups stay under the 3% daily cap).
**Withdrawal policy:** payout on the **14-day cadence**, withdraw **everything to breakeven**.

Key vs the earlier "converged" 3R/4R version (~$628/mo): **raising take-profits to 6R/8R
captures more of the NQ fat tail → +19% banked $/month**, robust in both data halves.

## Metrics (Monte-Carlo, block-bootstrap, COST=2pt)

| | value |
|---|---|
| **net banked $/month** | **$747** |
| avg total banked / account | $3,663 |
| median total banked / account | $2,192 |
| time to first payout | ~15 days |
| payouts before blow | ~3.2 |
| account lifespan | ~3.1 mo |
| blow rate | 100% |
| in-sample / out-of-sample | H1 $559 · H2 $949 |
| cost 1 / 2 / 3 pt | $824 / $747 / $677 |

**Net EV ≈ +$3,467 per funded account** (avg banked $3,663 − ~$196 to re-fund). 100% blow is
expected and *optimal*: extract ~$3.7k, the account dies, re-fund for ~$196, repeat.

## MT5 Strategy-Tester validation (independent)
5-yr tester run (2021→2026, NAS100, Vantage/TF Global, 100% real ticks) of the EA confirms
the engine and edge: **WR 25.5%** (model ~26%), **3,732 trades ≈ 3.0/day** (3 setups),
**expected payoff +$20.3/trade ≈ +0.12R** (model +0.10–0.13), **profit factor 1.16**.
The tester's **+$75,805** is the RAW *compounding* curve (risk = 0.67% of a growing balance,
no withdrawals, floor not enforced) — not the funded outcome. Its **39% max equity drawdown**
(worst dip below start −8.4%) confirms the floor is a real threat and why the funded account
blows without compounding. (Tester was the 3R/4R build; re-test the 6R/8R version to confirm.)

## What lost (explored across iterations 3–7)
- 4th (weak) session, higher-WR/low-R (tp2), fades, longer cadence (30/60d), bigger buffers,
  risk above ~$110 — all score lower. TP frontier peaks at 6R (4R $634, 6R $738, 8R $722,
  10–20R plateau); pullback edges slightly higher at 8R.

## Open thread (from the MT5 result)
The tester *compounded away from the floor* and survived 5 years (+$75k). A **compound-a-buffer-
first** policy (don't withdraw-to-BE; let the balance grow to e.g. $18–20k, then withdraw the
excess) may bank far more *total* than withdraw-to-BE (which blows 100% in ~3mo) — at the cost
of slower cash and early-DD blow risk. Needs %-of-balance sizing in the MC to model (next iter).

## Reproduce
`python3 funded_opt.py` (engine + bug-checks) · `funded_search.py` / `funded_search2.py` /
`funded_search3.py` / `funded_final.py` (the iteration search). EA: `FundedPhase.mq5`.

## Caveats
- Edge is 2022–2025 NAS100 in Python / 2021–2026 in the MT5 tester (bull-heavy); the 6R/8R
  configuration leans more on the fat tail than 3R/4R — re-validate live.
- Two trade windows (~04:00 ET EU + ~09:00 ET US) — run via the EA.
- Withdrawals are manual (14-day cadence to breakeven).
