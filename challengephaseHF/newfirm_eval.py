"""
challengephaseHF/newfirm_eval.py — 52p under a new CFD prop firm (50k), 1-step vs 2-step.
Rules from the user: 10% target, 12% max drawdown, 5% DAILY drawdown (2-step: P1 +10%, P2 +5%).
Much looser than FTMO (10% DD / 3% daily) — especially the 5% daily, which at 52p's risk basically
never binds, so the only real limit is the 12% overall DD. Models best-risk pass at 1/2/3-month
horizons; 2-step combined = P(phase1) x P(phase2-from-fresh). Static floor assumed (flag if the
firm trails). Run: python3 newfirm_eval.py
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
FLOOR = 0.88; DAILY = 0.05                            # 12% max DD, 5% daily
RISKS = (0.005, 0.006, 0.0075, 0.009, 0.01, 0.0125, 0.015)


def best(days, dl, target):
    br = (-1, None, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5, floor=FLOOR, daily=DAILY, target=target)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("52p under NEW FIRM 50k (10% target, 12% max DD, 5% daily) — best-risk pass\n")
    print(f"  {'structure':22}{'horizon':>10}{'risk':>7}{'PASS':>8}{'blow':>7}")
    for dl, lbl in [(20, "1 month"), (40, "2 months"), (60, "3 months")]:
        p, r, m = best(days, dl, 1.10)
        print(f"  {'1-STEP (+10%)':22}{lbl:>10}{r*100:6.2f}%{p*100:7.1f}%{m['blow_rate']*100:6.1f}%")
    print()
    # 2-step: P1 (+10%) then P2 (+5% from fresh). Combined = product at the same per-phase horizon.
    for dl, lbl in [(20, "1 month/phase"), (30, "1.5 month/phase")]:
        p1, r1, _ = best(days, dl, 1.10)
        p2, r2, _ = best(days, dl, 1.05)
        print(f"  {'2-STEP P1+10% P2+5%':22}{lbl:>10}{'':>7}  P1 {p1*100:4.1f}% x P2 {p2*100:4.1f}% = {p1*p2*100:4.1f}% funded")
    print()
    # FTMO 15k reference (10% target, 10% DD, 3% daily)
    for dl, lbl in [(40, "2 months")]:
        pf = -1
        for r in RISKS:
            m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5)  # FTMO defaults
            pf = max(pf, m["pass_rate"])
        print(f"  {'FTMO 15k (reference)':22}{lbl:>10}{'':>7}{pf*100:7.1f}%")
    print("\n" + "-"*66)
    print("The 5% daily basically never binds at 52p's risk, so the 12% DD (vs FTMO 10%) is the only")
    print("real constraint -> higher pass than FTMO. 1-step is a single +10%; 2-step needs BOTH phases")
    print("(product), so despite the easy +5% phase-2 it usually funds LESS often than the 1-step.")
    print("CFD/MT5 firm => your EA can run (confirm HEDGING + EET server). Assumes STATIC drawdown.")


if __name__ == "__main__":
    main()
