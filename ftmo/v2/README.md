# v2 — fresh NAS100 FTMO strategy search

A from-scratch rebuild (only the FTMO *rules* carried over from prior work) to find
the best NAS100 strategy for a fast, high-probability FTMO $15k 1-Step pass.
**Verdict and full numbers: see [`RESULTS.md`](RESULTS.md).**

## Code
| file | purpose |
|---|---|
| `data.py` | load/cache real US100 M1, audit quality + confirm timezone |
| `engine.py` | M1 fill simulator with costs + intraday MAE/MFE; trade→day aggregation |
| `ftmo.py` | FTMO 1-Step rule engine + day-bootstrap Monte-Carlo (all 5 rules, floating equity) |
| `strategies.py` | strategy library: `orb`, `or_fade`, `vwap_fade`, `orb_retest` |
| `run.py` | driver: backtest + MC scoreboard for a battery |
| `tune.py` | parameter sweeps |
| `batch3.py` | filters / alternate session / combos |
| `frontier.py` | capstone: robustness, deadline×risk frontier, daily-Sharpe proof |
| `scoreboard.py` | the definitive one-line-per-family table |

## Rules modeled (FTMO $15k 1-Step)
+10% target ($16,500) · static 10% floor ($13,500) · 3% daily loss · min 4 trading
days · 50% best-day consistency (soft). All checked on equity **including floating**.

## Quick start
```bash
python3 data.py        # build cache + audit (first run parses the raw CSV)
python3 scoreboard.py  # the family-by-family result table
python3 frontier.py    # deadline×risk frontier + why >80%/<3wk is impossible
```
Raw data and caches live in `../data_v2/` and `*.npz` (gitignored).
