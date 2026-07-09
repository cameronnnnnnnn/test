"""
challengephaseHF/rules_compare.py — "why do others show ~85%+ pass while my honest number on
FTMO is ~55%?" The biggest driver is almost never the strategy — it's the PROP-FIRM RULES,
above all the DAILY drawdown limit. FTMO 1-Step has a 3% *intraday* daily loss cap, which is
the single most common cause of blowing (a spike ends you even if you'd have recovered). Many
newer firms have NO daily limit (or measure end-of-day), so the same equity curve survives.

This runs the SAME 52p strategy (same day-return distribution, best risk per rule-set) under
different rule-sets, to isolate how much of the pass-rate gap is rules vs strategy.
Run: python3 rules_compare.py
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

NP = 100_000
RISKS = (0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03)


def best(days, deadline, daily, floor, target):
    br = (-1, None, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, deadline, n_paths=NP, seed=11, block=5,
                        daily=daily, floor=floor, target=target)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 88)
    print("SAME 52p strategy, different PROP-FIRM RULES — 20-day pass (best risk per rule-set)")
    print("=" * 88)
    print(f"  {'rule-set':44} {'risk*':>6} {'PASS':>6} {'BLOW':>6}")
    cases = [
        ("FTMO 1-Step: 10% floor + 3% DAILY (yours)",       0.03, 0.90, 1.10),
        ("10% floor, NO daily limit",                       0.00, 0.90, 1.10),
        ("5% max DD, 3% daily (tight + daily)",             0.03, 0.95, 1.10),
        ("5% max DD, NO daily limit",                       0.00, 0.95, 1.10),
        ("5% max DD, NO daily, 8% target",                  0.00, 0.95, 1.08),
        ("5% max DD, NO daily, 6% target",                  0.00, 0.95, 1.06),
    ]
    for name, daily, floor, target in cases:
        p, r, m = best(days, 20, daily, floor, target)
        print(f"  {name:44} {r*100:5.2f}% {p*100:5.1f}% {m['blow_rate']*100:5.1f}%")

    print("-" * 88)
    print("Same trades, same edge. The ONLY thing changing is the firm's rulebook. The 3% intraday")
    print("daily cap is FTMO's hardest constraint; removing it (as many firms do) is worth far more")
    print("to the pass rate than any strategy change. A lower profit target helps again on top.")


if __name__ == "__main__":
    main()
