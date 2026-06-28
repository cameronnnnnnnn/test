# FTMO funded-phase — optimized for net banked $/month (converged)

Objective: maximize **expected real banked dollars per month** = E[Σ your-90% withdrawals
over the account's life] ÷ lifetime, **net of amortized re-acquisition cost**. Convex-EV
principle: banked cash is permanent, the account's downside is capped at its cost, so we
optimize banked $ (not survival/win-rate) and front-load withdrawals.

Rules modeled (confirmed): $15,000 · 90/10 · static $13,500 floor (10%, no trail) · 3%
($450) intraday daily loss · payout cadence choosable 14/30/60d · min $20 / no max ·
**50% best-day consistency rule** (blocks payouts until the best winning day ≤ 50% of total
winning-day profit — doesn't fail the account).

## The winner

**Strategy (3 setups/day):**
- **US-open ORB** — 16:00 server (~09:00 ET), 30-min range, 60pt stop, 3R TP, volume-confirmed
- **EU-open ORB** — 11:00 server (~04:00 ET), 30-min range, 60pt stop, 3R TP, volume-confirmed
- **VWAP trend pullback** (US session) — 40pt stop, 4R TP

**Risk:** ~**$100 / trade** (≈0.67% of $15k; with 3 setups this stays under the 3% daily cap).
**Withdrawal policy:** request a payout on the **shortest (14-day) cadence**, withdraw
**everything down to breakeven ($15,000)** — the static floor keeps your full $1,500 cushion.

## Metrics (Monte-Carlo, block-bootstrap, COST=2pt)

| | withdraw to BE (max $/mo) | leave BE+$500 (more total) |
|---|---|---|
| **net banked $/month** | **$628** | $608 |
| avg total banked / account | $3,362 | $4,403 |
| median total banked / account | $2,058 | $2,411 |
| time to first payout | ~15 days | ~15 days |
| payouts before blow | ~3.8 | ~5.5 |
| account lifespan | ~3.5 mo | ~5 mo |
| blow rate | 100% | 99% |

**Amortized-cost-adjusted net EV ≈ +$3,166 per funded account** (avg banked $3,362 − ~$196 to
(re)acquire). 100% blow is *expected and optimal* here: you extract ~$3.4k, the account dies,
you re-fund for ~$196, repeat — a convex money machine, not a loss.

## Robustness & bug-check
- **In/out-of-sample:** H1 $480/mo · H2 $776/mo (full $628) — both halves solidly positive.
- **Cost sensitivity:** $701 / $628 / $559 per month at 1 / 2 / 3 pt round-turn.
- **Bug-checks (funded_opt.py):** 4 golden hand-cases (floor breach, daily breach, withdrawal,
  50%-rule block) + 3,000-path vectorized-vs-scalar equivalence — all pass; zero look-ahead.

## What lost (explored, no improvement)
- 4th setup (weak 10:00 session) dilutes → $608. Higher-WR/low-R (tp2) → $417. Fades → $352.
  Longer cadence (30/60d) and bigger buffers → lower $/mo. Risk above ~$110 hits the 3% daily cap.

## Reproduce
- `python3 funded_opt.py` — engine + funded rule model + bug-checks + risk×cadence×buffer grid.
- `python3 funded_search.py` — broad strategy search + in/out-of-sample + cost robustness.

## Caveats
- Edge is 2022–2025 NAS100 (bull-heavy); the EU-open ORB is the strongest leg and the most
  regime-sensitive (held in both halves, but watch it live).
- You trade two windows: EU morning (~04:00 ET) + US open (~09:00 ET) — consider an EA.
- Recommended practical pick: **BE+$250–500 buffer** — costs ~3% of the monthly rate but banks
  more total per account and dies slightly less abruptly. Pure $/month max is withdraw-to-BE.
