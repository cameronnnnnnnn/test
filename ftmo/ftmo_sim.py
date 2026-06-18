"""
FTMO 1-Step challenge engine + Monte Carlo.

Works in R-multiple / %-equity space (currency-agnostic; AUD account, USD pairs,
the conversion cancels for risk-based sizing). Leverage check done separately and
is never binding for these params (r*price/stopdist << 30).

Rules enforced (with the user's buffers):
  - Global loss: permanent FAIL if equity <= 0.905 * start (9.5% buffer; floor 9.0%).
  - Daily loss : stop NEW entries for the day if equity drops 2.8% from the day's
                 peak (resets each day).
  - Consistency: stop NEW entries for the day once today's P&L >= 45% of total P&L;
                 PASS requires biggest single-day profit <= 50% of total profit.
  - Min 3 trading days. Profit target +10% (equity >= 16,500). No time limit.
"""
import numpy as np
import pandas as pd

START = 15000.0
TARGET = START * 1.10          # 16,500
GLOBAL_HALT = START * 0.905    # 13,575 (9.5% buffer)
DAILY_BUF = 0.028
CONS_STOP = 0.45               # stop new entries when today >= 45% of total
CONS_PASS = 0.50               # pass needs max day <= 50% of total
MIN_DAYS = 3
MAX_DAYS = 300                 # safety cap (no real time limit)

def run_attempt(day_blocks, r, rng, sequential=False, start_idx=0):
    """Simulate one challenge. day_blocks: list of lists of R-floats (per day)."""
    equity = START
    total = 0.0
    day_profits = []
    n_days = 0
    idx = start_idx
    while n_days < MAX_DAYS:
        if sequential:
            if idx >= len(day_blocks):
                break
            day = day_blocks[idx]; idx += 1
        else:
            day = day_blocks[rng.integers(len(day_blocks))]
        day_peak = equity
        today = 0.0
        failed = False
        for R in day:
            if equity <= GLOBAL_HALT:
                failed = True; break
            if (day_peak - equity) / day_peak >= DAILY_BUF:   # daily halt -> no new entries
                break
            if total > 0 and today >= CONS_STOP * total:       # consistency buffer
                break
            pnl = r * R * equity
            equity += pnl
            today += pnl
            total += pnl
            if equity > day_peak:
                day_peak = equity
        n_days += 1
        day_profits.append(today)
        if failed or equity <= GLOBAL_HALT:
            return {"result": "FAIL_GLOBAL", "equity": equity, "days": n_days}
        if equity >= TARGET and n_days >= MIN_DAYS:
            wins = [p for p in day_profits if p > 0]
            if not wins or max(wins) <= CONS_PASS * total:
                return {"result": "PASS", "equity": equity, "days": n_days}
            # target hit but consistency not yet satisfied -> keep trading to dilute
    return {"result": "TIMEOUT", "equity": equity, "days": n_days}

def build_day_blocks(trades):
    blocks = []
    for _, g in trades.groupby("date", sort=True):
        blocks.append(list(g["R"].values))
    return blocks

def monte_carlo(trades, r, n=5000, seed=7):
    rng = np.random.default_rng(seed)
    blocks = build_day_blocks(trades)
    res = [run_attempt(blocks, r, rng) for _ in range(n)]
    df = pd.DataFrame(res)
    p = (df["result"] == "PASS").mean()
    fg = (df["result"] == "FAIL_GLOBAL").mean()
    to = (df["result"] == "TIMEOUT").mean()
    med_days = df[df["result"] == "PASS"]["days"].median() if p > 0 else float("nan")
    return {"pass": p, "fail_global": fg, "timeout": to, "med_days_to_pass": med_days, "n": n}
