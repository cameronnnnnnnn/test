"""
challengephaseHF/ger40_test.py — does GER40 (DAX) add a real, decorrelated edge to 52p? DAX is a
new market (European index, EET server, EU-open session 10:00 + US overlap 16-17). The hope: an
EU-session ORB edge that's less correlated with NAS100's US-session trades, so stacking it lifts
the monthly pass. Tests: (1) ORB edge vs RR at the EU + US opens (ATR stops, ~2pt cost), train/
test; (2) day-return correlation with 52p; (3) stacked 20-day pass vs 52p (risk on train + folds).
Run: python3 ger40_test.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52, fx_data            # noqa: E402

COST = 2.0; BREAKER = 2.0; DEADLINE = 20; NP = 40000
RISKS = (0.005, 0.0075, 0.01, 0.0125)


def split(ad, f=0.7):
    c = ad[int(len(ad)*f)]; return set(ad[ad <= c]), set(ad[ad > c])


def main():
    g = S.prep(fx_data.load("GER40")); nas = S.prep(data.load())
    atr = S.daily_atr(g, 14); sm = {d: 0.20*v for d, v in atr.items() if v == v}
    ad_g = np.array(sorted(g["date"].unique())); dtr, dte = split(ad_g)

    print("GER40 ORB edge (ATR stop, ~2pt cost)  — /day, WR, expR all/train/test")
    best = None
    for sess, om in [("EU 10:00", 10*60), ("US 16:00", 16*60)]:
        for rr in (2.0, 3.0, 4.0):
            tr = engine.simulate(g, S.orb(g, open_min=om, or_min=30, tp_R=rr, be_R=0.0,
                                 vol_filter=True, stop_map=sm), cost_pts=COST)
            e = engine.edge_stats(tr)
            etr = engine.edge_stats(tr[tr['day'].isin(dtr)])['expR']
            ete = engine.edge_stats(tr[tr['day'].isin(dte)])['expR']
            flag = "  <-- +OOS" if (etr > 0.02 and ete > 0.02) else ""
            print(f"  {sess} {rr:.0f}R  {e['n']/len(ad_g):.2f}/day  WR {e['wr']*100:4.1f}%  "
                  f"expR {e['expR']:+.3f}  ({etr:+.3f}/{ete:+.3f}){flag}")
            if etr > 0.02 and ete > 0.02 and (best is None or e['expR'] > best[1]):
                best = ((sess, om, rr), e['expR'], tr)
        print()

    # 52p reference + correlation + stack on common days
    p52 = engine.simulate(nas, CP52.build(nas), cost_pts=2.0)
    ad = np.array(sorted(set(nas["date"].unique()) & set(g["date"].unique())))
    def dser(tr): return np.asarray(build_days(tr[tr["day"].isin(set(ad))], ad, BREAKER)["day_R"], float)
    print(f"52p expR +{engine.edge_stats(p52)['expR']:.3f}   common days {len(ad)}")
    if best is None:
        print("\nNo GER40 ORB config holds OOS -> no decorrelated edge to add. DAX intraday is efficient too.")
        return
    (sess, om, rr), ex, gtr = best
    corr = np.corrcoef(dser(p52), dser(gtr))[0, 1]
    print(f"BEST GER40 leg: {sess} {rr:.0f}R  expR +{ex:.3f}   corr with 52p = {corr:+.2f}\n")

    dtr2, dte2 = split(ad)
    folds = np.array_split(ad, 4)
    def mc(ds, r): return ftmo.run_mc(ds, r, DEADLINE, n_paths=NP, seed=11, block=5)
    def br(ds): return max(RISKS, key=lambda r: mc(ds, r)["pass_rate"])
    def ev(parts, tag):
        t = pd.concat(parts, ignore_index=True)
        r = br(build_days(t[t["day"].isin(dtr2)], np.array(sorted(dtr2)), BREAKER))
        te = mc(build_days(t[t["day"].isin(dte2)], np.array(sorted(dte2)), BREAKER), r)
        fps = [mc(build_days(t[t["day"].isin(set(f))], f, BREAKER),
                  br(build_days(t[t["day"].isin(set(np.concatenate([x for x in folds if x[0]!=f[0]])))],
                     np.concatenate([x for x in folds if x[0]!=f[0]]), BREAKER)))["pass_rate"] for f in folds]
        print(f"  {tag:26} r*={r*100:4.2f}%  TE {te['pass_rate']*100:4.1f}%  blow {te['blow_rate']*100:4.1f}%"
              f"  foldMean {np.mean(fps)*100:4.1f}% worst {np.min(fps)*100:4.1f}%")
    pc = p52[p52["day"].isin(set(ad))]; gc = gtr[gtr["day"].isin(set(ad))]
    print("STACK (20-day pass, risk on train):")
    ev([pc], "52p alone")
    ev([pc, gc], "52p + GER40 leg")
    print("-"*72)
    print("Adds value only if TE and worst-fold rise vs 52p alone AND corr is low. Equity indices")
    print("usually correlate, so watch the corr — an EU-session leg is the best shot at decorrelation.")


if __name__ == "__main__":
    main()
