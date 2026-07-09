"""
challengephaseHF/pass_time.py — how LONG does a fresh 15k take to pass at 0.5% vs 0.75%?
0.5% passes more eventually (~80%) but sizes tiny, so it grinds slowly. This reports the
cumulative pass curve and the median/mean trading-days-to-pass (translated to calendar months
at ~21 trading days/month), so the speed/safety trade-off is concrete. Run: python3 pass_time.py
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
TDPM = 21.0        # ~trading days per calendar month


def main():
    bal = float(sys.argv[1]) if len(sys.argv) > 1 else 15000.0
    e0 = bal / 15000.0
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 74)
    tag = "Fresh FTMO 15k" if e0 == 1.0 else f"FTMO 15k from ${bal:,.0f} (down {(1-e0)*100:.2f}%)"
    print(f"{tag} — how long to pass?  (cumulative pass % by trading day)")
    print("=" * 74)
    cols = [20, 30, 40, 60, 80, 100, 120]
    print(f"  {'risk':>6}  " + "".join(f"{f'd{d}':>7}" for d in cols) + f"  {'≈months@pass':>13}")
    for risk in (0.005, 0.0075):
        row = f"  {risk*100:5.2f}% "
        for d in cols:
            row += f"{ftmo.run_mc(days, risk, d, n_paths=NP, seed=11, block=5, e0=e0)['pass_rate']*100:6.1f}"
        m = ftmo.run_mc(days, risk, 120, n_paths=NP, seed=11, block=5, e0=e0)
        med, mean = m["med_days_to_pass"], m["mean_days_to_pass"]
        row += f"    med {med:.0f}d/{med/TDPM:.1f}mo"
        print(row)
        print(f"         {'':>{7*len(cols)}}  mean {mean:.0f}d ≈ {mean/TDPM:.1f}mo  (among passers)")
    print("-" * 74)
    print("Read: dN = % of accounts passed by trading-day N (20d≈1mo, 40d≈2mo, 60d≈3mo).")
    print("0.5% keeps climbing for months (slow grind, few blows); 0.75% front-loads the passes")
    print("in the first ~month but plateaus lower (more blow early). Pick by your timeline.")


if __name__ == "__main__":
    main()
