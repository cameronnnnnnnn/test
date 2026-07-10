"""
challengephaseHF/opt_horizon.py — best 52p pass rate when you OPTIMISE risk for a given horizon.
Sweeps risk at each deadline and reports the max pass + the risk that gets it (fresh 15k, FTMO).
Answers "what's the optimised pass if I'm willing to take ~2 months (40 trading days)?"
Run: python3 opt_horizon.py
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

NP = 120_000
RISKS = (0.0035, 0.004, 0.005, 0.006, 0.0075, 0.009, 0.01)


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("Fresh FTMO 15k — best pass when risk is OPTIMISED for the horizon:")
    print(f"  {'horizon':>16}   {'best risk':>9}   {'PASS':>6}   {'blow':>6}")
    for dl, lbl in [(20, "1 month (20d)"), (40, "2 months (40d)"), (60, "3 months (60d)")]:
        best = (-1, None, None)
        for r in RISKS:
            m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        print(f"  {lbl:>16}   {r*100:8.2f}%   {p*100:5.1f}%   {m['blow_rate']*100:5.1f}%")
    print("\n(2-month row is the answer: gives the edge more time to compound at a lower, safer risk.)")


if __name__ == "__main__":
    main()
