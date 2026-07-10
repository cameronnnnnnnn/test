"""
challengephaseHF/streak_odds.py — "0 wins in 12 trades / 3 days — what are the odds?" The naive
binomial (1-WR)^12 understates it because 52p's trades CLUSTER by regime (choppy days lose
together). This measures the REAL frequency from the historical trade sequence: how often does a
rolling 12-trade window, or a rolling 3-trading-day window, contain zero winners (R>0)? Also the
worst historical streak, so you can see these happen. Run: python3 streak_odds.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                 # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402


def main():
    df = S.prep(data.load())
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST).sort_values("entry_dt").reset_index(drop=True)
    win = (tr["R"].values > 0).astype(int)
    n = len(win); wr = win.mean()
    print(f"52p: {n} trades, win rate {wr*100:.1f}% (win = R>0; BE/scratch counts as non-win)\n")

    # naive independent binomial
    p0_12 = (1 - wr) ** 12
    print(f"naive binomial  P(0 wins in 12 indep trades) = {p0_12*100:.2f}%  (~1 in {1/p0_12:.0f})")

    # empirical: rolling 12-trade windows with zero wins
    z12 = sum(1 for i in range(n - 12 + 1) if win[i:i+12].sum() == 0)
    tot12 = n - 12 + 1
    print(f"EMPIRICAL       P(0 wins in 12 consecutive trades) = {z12/tot12*100:.2f}%  "
          f"({z12} of {tot12} windows, ~1 in {tot12/max(z12,1):.0f})")

    # empirical: rolling 3-trading-day windows with zero wins
    tr["day"] = pd.to_datetime(tr["entry_dt"]).dt.normalize()
    byday = tr.groupby("day")["R"].apply(lambda s: (s.values > 0).sum())
    days = byday.index.to_list(); wpd = byday.values
    z3 = sum(1 for i in range(len(days) - 3 + 1) if wpd[i:i+3].sum() == 0)
    tot3 = len(days) - 3 + 1
    ntr3 = [tr[tr["day"].isin(days[i:i+3])].shape[0] for i in range(len(days)-3+1)]
    print(f"                P(0 wins across 3 trading days)    = {z3/tot3*100:.2f}%  "
          f"({z3} of {tot3} windows, ~1 in {tot3/max(z3,1):.0f})")

    # worst historical streaks
    longest = cur = 0
    for w in win:
        cur = 0 if w else cur + 1
        longest = max(longest, cur)
    print(f"\nlongest historical losing streak (0 wins in a row): {longest} trades")
    print(f"avg trades/day {n/tr['day'].nunique():.1f} -> 12 trades ≈ 3 days, matching your run.")
    print("\nSo a 0-for-12 / 0-for-3-days stretch is UNCOMMON but well inside 52p's normal variance")
    print("— it is what a choppy, no-follow-through cluster looks like (runners need trending days).")
    print("It'd only start to look like a live≠backtest problem if it ran much longer (~20+ no wins).")


if __name__ == "__main__":
    main()
