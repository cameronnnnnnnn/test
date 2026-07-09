"""
challengephaseHF/two_account.py — "I don't care if I blow 2 accounts" — so which risk actually
uses that 2-account budget best? Runs accounts SEQUENTIALLY (buy the next only if the prior
blows) and reports P(at least one passes) and the EXPECTED number of accounts you'll buy, at
0.5% vs 0.75%. Point: a backup budget is an argument for LOWER per-account risk, not higher —
lower risk passes the first account more often, so you spend less AND end up more likely to pass.
Run: python3 two_account.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402

NP = 120_000; FEE = 132.0; RESOLVE = 150     # run each account to (near) full resolution


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 78)
    print("Using a 'up to 2 accounts' budget — sequential (buy #2 only if #1 blows), $132 each")
    print("=" * 78)
    print(f"  {'risk':>6}  {'1 acct pass':>11}  {'blow':>6}  |  {'2 accts: P(≥1 pass)':>19}  {'E[accts bought]':>15}  {'E[spend]':>9}")
    for risk in (0.005, 0.0075):
        m = ftmo.run_mc(days, risk, RESOLVE, n_paths=NP, seed=11, block=5)
        p_pass = m["pass_rate"]; p_blow = m["blow_rate"]      # ~sums to 1 at full resolution
        p2 = 1 - p_blow**2                                    # at least one of two passes
        e_accts = 1 + p_blow                                  # buy #2 only if #1 blew
        print(f"  {risk*100:5.2f}%  {p_pass*100:10.1f}%  {p_blow*100:5.1f}%  |  "
              f"{p2*100:18.1f}%  {e_accts:15.2f}  ${e_accts*FEE:8.0f}")
    print("-" * 78)
    print("Read: 0.5% passes the FIRST account far more often, so you usually spend ONE $132 and")
    print("rarely touch the backup — yet you're MORE likely to pass across the budget. 0.75% blows")
    print("the first account more, so you buy the 2nd more often AND end up less likely to pass.")
    print("The 2-account cushion is the reason you can AFFORD 0.5% — not a reason to run hot.")


if __name__ == "__main__":
    main()
