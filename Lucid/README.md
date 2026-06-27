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
- Funded-phase payout rules (min 5 trading days, min 5 days of $100+) are not yet modeled —
  this covers the **eval** (passing) only.
