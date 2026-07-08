"""
challengephaseHF/conditional_mc.py — "from where I am NOW, what are the odds?" The account is
mid-challenge in drawdown, not at a fresh $15k start. This runs the 52p Monte-Carlo starting
from the CURRENT balance (e0 = current/15000) so pass/blow are conditional on the real state,
at both the current 0.75% risk and a defensive 0.50%. Target is still +10% of the ORIGINAL
(15,000 -> 16,500) and the floor is still the static 13,500, exactly as FTMO scores it.

Usage: python3 conditional_mc.py [current_balance]   (default 14134.72)
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

START = 15000.0
NP = 120_000


def main():
    cur = float(sys.argv[1]) if len(sys.argv) > 1 else 14134.72
    e0 = cur / START
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 72)
    print(f"52p — conditional odds FROM ${cur:,.2f}  (e0={e0:.4f}, down {(1-e0)*100:.2f}%)")
    print(f"target ${START*1.10:,.0f} (need +{(1.10/e0-1)*100:.1f}% from here) · floor ${START*0.90:,.0f} "
          f"(${cur-START*0.90:,.0f} = {(e0-0.90)*100:.2f}% buffer)")
    print("=" * 72)
    print(f"  {'risk':>6}  {'horizon':>9}   {'PASS':>6}  {'BLOW':>6}  {'still going':>11}")
    for risk in (0.0075, 0.005):
        for dl, lbl in [(20, "20 days"), (60, "60 days")]:
            m = ftmo.run_mc(days, risk, dl, n_paths=NP, seed=11, block=5, e0=e0)
            print(f"  {risk*100:5.2f}%  {lbl:>9}   {m['pass_rate']*100:5.1f}%  {m['blow_rate']*100:5.1f}%  "
                  f"{m['timeout_rate']*100:10.1f}%")
        print()
    print("Reading it: BLOW = hit the 13,500 floor (fail). 'still going' = neither yet (no time")
    print("limit, so those keep trying). Lower risk => much lower blow, slower climb to target.")
    print("Caveat: assumes the future resembles the full 3yr sample; a persistent chop regime")
    print("(like the last two sessions) would run worse than this near-term.")


if __name__ == "__main__":
    main()
