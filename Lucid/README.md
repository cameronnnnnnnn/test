# Lucid — 25K FLEX EVAL strategy (NQ/MNQ futures)

A from-scratch strategy + Monte-Carlo built for the **25K FLEX EVAL** ruleset (a futures
prop eval, *not* FTMO). Goal: maximize the **monthly passing rate**.

## The ruleset (from the card)
| | |
|---|---|
| Account | **$25,000** |
| Profit target | **+$1,250 (5%)** |
| Max loss | **$1,000 (4%)** — **EOD trailing** drawdown |
| Daily loss limit | **NONE** |
| Consistency | **50%** (eval); none in funded |
| Max size | **2 minis OR 20 micros** (NQ: $40/index-point cap) |
| Eval fee | **$70** (reset **$60**) |

**EOD trailing drawdown** = the floor trails your highest *end-of-day* balance
(`floor = max(EOD balances) − $1,000`). Intraday peaks don't raise it, and — consistent
with "no daily loss limit" — the breach is judged on the **end-of-day** balance (you can
swing intraday and recover). This is the single most important rule; `breach="intraday"`
(stricter) is ~1pp lower, so the result is robust either way.

Why this is hard: the **$1,000 trailing DD (4%) is tighter than the +$1,250 target (5%)**,
so you must out-run a drawdown smaller than your goal — with NQ's thin intraday edge that
caps the monthly pass at **~40–42%** (a structural ceiling, confirmed across many strategies).

## The strategies (verified)
30-minute **Opening-Range Breakout**, 60-pt stop, **3R** take-profit, volume-confirmed,
**2 MNQ micros** ($240 risk/trade). Server time = ET+7 (EET).

| | session (server / ET) | monthly pass | eventual pass | blow | $/funded |
|---|---|---|---|---|---|
| **[A] best monthly** | 11:00 / ~04:00 ET (EU open) | **42.4%** | 49% | 51% | $132 |
| [B] convenient | 16:00 / ~09:00 ET (US open) | 40.1% | 45% | 55% | $142 |
| **[C] best to get funded** | both sessions, **1 micro** | 36% | **57%+** | 42% | **$115** |

- **Pass this month →** [A] European-open ORB, 2 micros (~42%).
- **Get funded cheaply (evals have no time limit) →** [C] trade both sessions at 1 micro:
  diversification roughly halves the blow rate and lifts eventual pass to ~57%+ → ~$115 per
  funded $25k account. Best EV.
- **Sizing is tiny on purpose** — the tight trailing DD punishes size. Never use the 2-mini
  cap (~$2,400/trade → instant blow).

The edge is **robust**: expR +0.147 (first half) / +0.165 (second half) for the EU ORB, and
holds at costs from 0.5 to 2.5 index-pt round-turn.

## Funded phase + efficiency vs FTMO (`lucid_funded.py`)
Funded rules: $25k, $1k DD that **locks at breakeven ($25,000)** once you're +$1k, no daily
limit, 90/10 split, payout = 50% of profit capped $1,000/req, min $500, after 5 trading
days + 5 days of $100+. Modeled on the same engine (golden-checked), vs an FTMO 15k funded
account modeled identically.

| funded account | avg income | median | blow | avg life | cost/funded | **avg income / $ spent** |
|---|---|---|---|---|---|---|
| **Lucid 25k** (1 micro, realistic min) | $1,316 | $929 | ~100% / ~3mo | 3.1 mo | $112 | **11.7×** |
| **FTMO 15k** (finely sizable) | $4,300–5,800 | $4,350–5,980 | 9–56% / survives | 17–23 mo | $196 | **~30×** |

**Verdict: FTMO is ~2.5× (avg) to ~3.7× (median) MORE efficient per eval-dollar — the
opposite of the "bigger/cheaper ⇒ better" intuition.** Why:
- **Lucid's floor locks *at* breakeven** → cushion shrinks to ~$500–1,000 and any return to
  breakeven = death → ~100% blow in ~3 months, ~2.5 payouts. Cheap to fund, but earns little.
- **FTMO's floor sits $1,500 *below* breakeven (static)** → permanent cushion that doesn't
  shrink with withdrawals → survives ~20 months, ~20–26 payouts; even accounts that
  eventually blow have banked ~$5k first.
- Lucid (futures) can't size below 1 micro = $120/trade without tightening the stop, which
  *degrades* the edge (25pt → expR +0.09); FTMO (CFD) sizes finely and runs safer.

Both are still net +EV (Lucid ~+$1,200/funded, FTMO ~+$5,600/funded) — Lucid is just the
less efficient of the two. Lucid's edge is purely **lower cost-to-fund** (~1.75×); FTMO wins
decisively on **income per funded account** (~4×), so FTMO wins overall.

## Files
- `lucid.py` — rule engine + Monte-Carlo (`run_eval_mc`): EOD trailing DD, target,
  50% consistency, no daily limit, fixed/buffer sizing, EOD/intraday breach.
- `strategy_lucid.py` — final results table (run this). `python3 strategy_lucid.py`
- `search.py` / `search2.py` / `search3.py` — the strategy search (rounds 1–3).
- `confirm.py` — winner at real integer-micro sizes + EV.
- `test_lucid.py` — **bug-check**: 8 hand-computed golden cases + full vectorized-vs-scalar
  equivalence (both breach modes) + zero-look-ahead engine checks. `python3 test_lucid.py`
- `engine.py` / `strategies.py` / `data.py` — reused bug-fixed core (NAS100 M1 = NQ proxy).

## Caveats
- Data is ~3 years (2022–2025), mostly a bull regime; ORB edges are partly trend-driven.
- The European-session edge trades at ~04:00 ET (early for US traders) — consider automating,
  or use [B] (US open, 09:00 ET) for ~2pp less.
- Costs/fills modeled conservatively; verify your broker's MNQ commissions + slippage.
- Funded model assumes the 5-day/$100 rule is a one-time unlock + 5-day payout cadence, and
  withdraw-max each cycle; the dominant driver (floor *at* vs *below* breakeven) is structural
  and robust to those assumptions.
