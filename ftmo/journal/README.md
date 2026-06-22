# ORB trade journal — tracking, debriefs, and a database that compounds

A single-file SQLite database of every trade your EA takes, plus a debrief generator that
scores the account against FTMO's limits and against the backtest edge. The point: your
live history accumulates in `orb_journal.db`, so over time you can re-run the same
Monte-Carlo / regime analysis on your *real* fills and keep improving.

## Why this design
- **SQLite** — one file, no server, full SQL, ideal at this scale, syncs into the repo.
- **CSV bridge from the EA** — your MT5 runs on Linux/Wine, where the `MetaTrader5`
  python package doesn't run cleanly. Having the EA append each closed trade to a CSV is
  bulletproof and OS-independent.
- **R-multiples computed like the backtest** (`price move ÷ stop`), so live stats line up
  directly with the MC numbers (expR ≈ +0.125, WR ≈ 31%).

## Quick start
```bash
cd ftmo/journal
python3 orb_journal.py init                                   # create the DB
python3 orb_journal.py ingest history.csv --stop 80 --start 15000
python3 orb_journal.py debrief --start 15000 --out debrief.md # print + save report
```
Re-ingesting is safe — trades are keyed by ticket (`INSERT OR REPLACE`), so you can run it
repeatedly and it just updates.

## Getting trade data out of MT5 — two ways

### Option A (recommended, automated): EA writes the CSV itself
Paste the block in **`ea_logging_snippet.mq5`** into `NAS100_ORB_sprint.mq5`, recompile,
re-attach. It appends every closed position to `MQL5/Files/ORB_journal.csv` in exactly the
format this tool ingests. Do the swap when the market is closed so you don't interrupt a
live position. Then on the VM:
```bash
python3 orb_journal.py ingest ~/.wine/drive_c/.../MQL5/Files/ORB_journal.csv
```

### Option B (immediate, no EA change): manual MT5 export
MT5 → **Toolbox → History** tab → right-click → **Report → Save as CSV**. Ingest that file
directly — the column names are auto-detected.

## Daily routine on the VM (optional automation)
Record an equity snapshot and regenerate the debrief once a day (e.g. via `cron`):
```bash
python3 orb_journal.py snapshot --balance 15123 --equity 15098
python3 orb_journal.py ingest .../ORB_journal.csv && python3 orb_journal.py debrief --out debrief.md
```

## What the debrief tells you
- **FTMO status**: balance, P&L vs +10% target, cushion to the 10% trailing-DD floor,
  today's P&L vs the 3% daily stop (with a warning when you're getting close).
- **Live edge** vs the backtest: trades, win rate, expectancy (R), profit factor — flags
  if the live edge drifts below backtest.
- **Splits** by session (15/16) and direction (buy/sell), plus your last 10 trades.

## How this feeds back into improving the strategy
Once you have a few dozen live trades, export the DB and you can:
- compare live expR / WR / max-R to the backtest (is the edge holding?),
- tag live trades by volatility regime and re-run `mc_regime_switching.py` on real fills,
- confirm whether the **long-only** and **risk** findings hold out of sample.

The database is the asset — it turns every trade into a data point for the next iteration.
```
db schema:  trades(ticket, symbol, direction, volume, open/close time+price, sl,
                   profit, commission, swap, session, r_multiple, comment)
            snapshots(ts, balance, equity, note)
```
