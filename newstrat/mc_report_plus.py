"""
newstrat/mc_report_plus.py — full 100k+ Monte-Carlo report for ChallengePhase52pPlus under FTMO
15k 1-Step rules (mirror of challengephaseHF/mc_report.py for the Plus build). Pass/blow/timeout,
mean+median days-to-pass, daily-vs-overall blow split, cumulative pass curve, risk sensitivity,
all-data AND out-of-sample. Run: python3 mc_report_plus.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3"), ("..", "challengephaseHF")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import engine, ftmo                                     # noqa: E402
from search import build_days                            # noqa: E402
import ChallengePhase52pPlus as P                         # noqa: E402

NP = 120_000


def main():
    tr, ad = P.trades()
    es = engine.edge_stats(tr)
    cut = ad[int(len(ad)*0.7)]; te = ad[ad > cut]
    d_all = build_days(tr, ad, P.BREAKER)
    d_oos = build_days(tr[tr["day"].isin(set(te))], te, P.BREAKER)

    print("=" * 78)
    print(f"ChallengePhase52pPlus — {NP:,}-path Monte Carlo, FTMO 15k 1-Step")
    print("8 legs (52p x4 + fade|range + tom + Monday + GER40-close), -2R breaker")
    print("=" * 78)
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  {es['n']/len(ad):.1f} trades/day  "
          f"({es['n']} trades / {len(ad)} days)\n")

    for risk in (0.0075, 0.005):
        print(f"────────────── RISK {risk*100:.2f}% {'(20-day sprint optimum)' if risk==0.0075 else '(2-month safe profile)'} ──────────────")
        for lbl, dd in [("ALL DATA ", d_all), ("OUT-OF-SAMPLE", d_oos)]:
            m = ftmo.run_mc(dd, risk, 20, n_paths=NP, seed=11, block=5)
            print(f"  [{lbl}]  20 trading days (1 month):")
            print(f"    PASS  {m['pass_rate']*100:5.1f}%   FAIL/blow {m['blow_rate']*100:5.1f}%   "
                  f"timeout {m['timeout_rate']*100:5.1f}% (keeps trading, not a loss)")
            print(f"    blows: {m['blow_daily_share']*100:.0f}% daily-3% cap / {(1-m['blow_daily_share'])*100:.0f}% overall floor"
                  f"   | days-to-pass: mean {m['mean_days_to_pass']:.1f}, median {m['med_days_to_pass']:.0f}")
        row = "  cumulative pass (ALL):"
        for dl in (10, 20, 30, 40, 60):
            row += f"  d{dl} {ftmo.run_mc(d_all, risk, dl, n_paths=NP, seed=11, block=5)['pass_rate']*100:.1f}%"
        m60 = ftmo.run_mc(d_all, risk, 60, n_paths=NP, seed=11, block=5)
        print(row)
        print(f"  eventual (60d): pass {m60['pass_rate']*100:.1f}% vs blow {m60['blow_rate']*100:.1f}%\n")

    print("RISK SENSITIVITY (ALL data, 20-day pass / blow):")
    print("   " + "".join(f"{r*100:>8.2f}%" for r in (0.004, 0.005, 0.006, 0.0075, 0.009, 0.01)))
    for key, tag in [("pass_rate", "pass"), ("blow_rate", "blow")]:
        row = f"  {tag:>5}"
        for r in (0.004, 0.005, 0.006, 0.0075, 0.009, 0.01):
            row += f"{ftmo.run_mc(d_all, r, 20, n_paths=NP, seed=11, block=5)[key]*100:8.1f}"
        print(row)


if __name__ == "__main__":
    main()
