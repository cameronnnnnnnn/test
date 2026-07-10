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
        m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5, floor=FLOOR, daily=DAILY,
                        target=target, consistency=False)      # this firm has NO consistency rule
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("52p under NEW FIRM 50k — 10% target, 12% STATIC max DD, 5% daily, NO consistency, 30-DAY MAX\n")
    print(f"  {'structure':22}{'deadline':>18}{'risk':>7}{'PASS':>8}{'blow':>7}")
    # 30-day max: 30 calendar ~= 22 trading days; or 30 trading days. Bracket both.
    for dl, lbl in [(22, "30 cal (~22 td)"), (30, "30 trading days")]:
        p, r, m = best(days, dl, 1.10)
        print(f"  {'1-STEP (+10%)':22}{lbl:>18}{r*100:6.2f}%{p*100:7.1f}%{m['blow_rate']*100:6.1f}%")
    print()
    for dl, lbl in [(22, "30 cal / phase"), (30, "30 td / phase")]:
        p1, _, _ = best(days, dl, 1.10); p2, _, _ = best(days, dl, 1.05)
        print(f"  {'2-STEP P1+10% P2+5%':22}{lbl:>18}{'':>7}  P1 {p1*100:4.1f}% x P2 {p2*100:4.1f}% = {p1*p2*100:4.1f}% funded")
    print()
    pf = max(ftmo.run_mc(days, r, 40, n_paths=NP, seed=11, block=5)["pass_rate"] for r in RISKS)
    print(f"  {'FTMO 15k (ref, 2mo, no deadline)':38}{pf*100:7.1f}%")

    # --- cost per funded account (fee / fund-rate): the funded 50k is identical, so cheapest wins ---
    print("\n" + "="*72)
    print("COST PER FUNDED 50k ACCOUNT (fee / fund-rate) — lower is better; funded value is equal")
    print("="*72)
    FEE1, FEE2 = 238.0, 154.0
    for lbl, dl in [("30 calendar (~22 td)", 22), ("30 trading days", 30)]:
        p1s, _, _ = best(days, dl, 1.10)                       # 1-step fund rate
        pp1, _, _ = best(days, dl, 1.10); pp2, _, _ = best(days, dl, 1.05)
        f2 = pp1 * pp2                                          # 2-step fund rate
        print(f"  [{lbl}]  1-STEP ${FEE1:.0f}/{p1s*100:.0f}% = ${FEE1/p1s:.0f}   "
              f"2-STEP ${FEE2:.0f}/{f2*100:.0f}% = ${FEE2/f2:.0f}   "
              f"-> {'2-STEP' if FEE2/f2 < FEE1/p1s else '1-STEP'} cheaper")
    print("  (20% reset discount lowers BOTH ~proportionally, so the ranking holds. But the 2-step")
    print("   needs two 30-day phases = up to 60 days > your 56-day window if a phase runs long.)")
    print("\n" + "-"*72)
    print("The 30-DAY MAX is the catch: you must hit +10% in ~22-30 trading days, so pass is LOWER")
    print("than the no-deadline 76%, and optimal risk is HIGHER (must move faster). No consistency")
    print("rule + static 12% DD still help. 2-step needs both phases IN TIME -> funds less, and two")
    print("30-day phases (up to 60 days) may overrun your 56-day birthday window. PLATFORM: Match")
    print("Trader does NOT run .mq5 EAs -> needs a trade copier from MT5, or a rewrite.")


if __name__ == "__main__":
    main()
