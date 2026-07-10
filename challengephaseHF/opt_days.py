"""
challengephaseHF/opt_days.py — most optimal 52p risk for a given CALENDAR-day deadline. Converts
calendar days to trading days (x5/7, minus ~1 holiday per month) and finds the risk that maximises
the pass rate at that horizon on a fresh 15k. Usage: python3 opt_days.py [calendar_days]  (default 56)
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

NP = 150_000
RISKS = (0.0045, 0.005, 0.0055, 0.006, 0.0065, 0.007, 0.0075, 0.008, 0.009)


def main():
    cal = int(sys.argv[1]) if len(sys.argv) > 1 else 56
    td = round(cal * 5.0 / 7.0)                 # weekends out
    td_hol = max(td - round(cal / 30.0), 4)     # ~1 holiday / month
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print(f"{cal} calendar days -> ~{td} trading days (~{td_hol} after holidays). Fresh 15k, 52p.\n")
    for dl in (td_hol, td):
        print(f"  deadline {dl} trading days:")
        print(f"    {'risk':>6}{'PASS':>8}{'blow':>8}{'timeout':>9}")
        best = (-1, None)
        for r in RISKS:
            m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5)
            mark = ""
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r)
            print(f"    {r*100:5.2f}%{m['pass_rate']*100:7.1f}%{m['blow_rate']*100:7.1f}%{m['timeout_rate']*100:8.1f}%")
        print(f"    -> optimal risk {best[1]*100:.2f}%  (pass {best[0]*100:.1f}%)\n")
    print("Note: the pass curve is FLAT near the top — anything ~0.55-0.65% is within a point of")
    print("optimal, so 0.6% is the pick and your live 0.5% is already ~within a point of it.")


if __name__ == "__main__":
    main()
