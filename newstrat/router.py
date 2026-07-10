"""
newstrat/router.py — iteration 3: does prior-day regime routing ADD pass rate to 52p? The matrix
found OOS-stable regime edges: NAS100 fade|prior-day-range (+0.11/+0.20), USDJPY momentum|range+
unclear (+0.09/+0.11, +0.06/+0.06). These are decorrelated from 52p's momentum and fire on
different days, so they should smooth the curve. Test honestly: stack each onto 52p, risk picked
on TRAIN, pass reported on TEST + 4-fold. Anti-overfit: the regime->setup mapping is principled
(fade in range, momentum otherwise), standard thresholds, and only counted if it lifts TEST +
worst-fold, not just all-data. Run: python3 router.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine, ftmo                  # noqa: E402
from search import build_days                          # noqa: E402
import ChallengePhase52p as CP52                        # noqa: E402
import allinstr                                         # noqa: E402
from regime_matrix import regime_map, SESS             # noqa: E402

BREAKER = 2.0; DEADLINE = 20; NP = 40000
RISKS = (0.005, 0.0075, 0.01, 0.0125)


def mc(ds, r): return ftmo.run_mc(ds, r, DEADLINE, n_paths=NP, seed=11, block=5)
def best_risk(ds): return max(RISKS, key=lambda r: mc(ds, r)["pass_rate"])


def gated(tr, days_keep):
    return tr[tr["day"].isin(set(days_keep))] if len(tr) else tr


def main():
    D = allinstr.load_all(verbose=False)
    # --- 52p baseline (NAS100) ---
    nas = D["NAS100"]["df"]; smN = allinstr.stopmap(D["NAS100"], 0.20)
    p52 = engine.simulate(nas, CP52.build(nas), cost_pts=2.0)
    rN = regime_map(nas)
    nas_range_days = [d for d in nas["date"].unique() if rN.get(d) == "range"]
    # NAS100 fade, only on prior-day-range days (the new regime edge)
    nas_fade = gated(engine.simulate(nas, S.vwap_fade_sel(nas, k=2.0, open_min=SESS["NAS100"],
                     trail_R=2.0, partial_R=1.0, stop_map=smN), cost_pts=2.0), nas_range_days)
    # USDJPY momentum, only on range+unclear prior-day regimes
    jpy = D["USDJPY"]["df"]; smJ = allinstr.stopmap(D["USDJPY"], 0.20)
    rJ = regime_map(jpy)
    jpy_days = [d for d in jpy["date"].unique() if rJ.get(d) in ("range", "unclear")]
    jpy_mom = gated(engine.simulate(jpy, S.orb(jpy, open_min=SESS["USDJPY"], or_min=30, tp_R=4.0,
                    be_R=0.0, vol_filter=True, stop_map=smJ), cost_pts=D["USDJPY"]["cost"]), jpy_days)

    ad = np.array(sorted(set(nas["date"].unique()).intersection(set(jpy["date"].unique()))))
    def clip(t): return t[t["day"].isin(set(ad))]
    p52, nas_fade, jpy_mom = clip(p52), clip(nas_fade), clip(jpy_mom)
    cut = ad[int(len(ad)*0.7)]; dtr, dte = ad[ad <= cut], ad[ad > cut]
    folds = np.array_split(ad, 4)

    for nm, tr in [("52p", p52), ("NAS fade|range", nas_fade), ("USDJPY mom|rng+unc", jpy_mom)]:
        e = engine.edge_stats(tr) if len(tr) else dict(n=0, wr=0, expR=0)
        print(f"  {nm:20} n={e['n']:4d} {e['n']/len(ad):4.2f}/day  WR {e['wr']*100:4.1f}%  expR {e['expR']:+.3f}")

    def stack(parts, tag):
        t = pd.concat(parts, ignore_index=True)
        dtr_s = build_days(t[t["day"].isin(set(dtr))], dtr, BREAKER)
        dte_s = build_days(t[t["day"].isin(set(dte))], dte, BREAKER)
        r = best_risk(dtr_s)
        fps = [mc(build_days(t[t["day"].isin(set(f))], f, BREAKER),
                  best_risk(build_days(t[t["day"].isin(set(np.concatenate([x for x in folds if x[0]!=f[0]])))],
                                       np.concatenate([x for x in folds if x[0]!=f[0]]), BREAKER)))["pass_rate"] for f in folds]
        m = mc(dte_s, r)
        print(f"  {tag:34} r*={r*100:4.2f}%  TE {m['pass_rate']*100:4.1f}%  blowTE {m['blow_rate']*100:4.1f}%"
              f"  foldMean {np.mean(fps)*100:4.1f}% foldWorst {np.min(fps)*100:4.1f}%")

    print("\n" + "="*88)
    print(f"REGIME-ROUTED STACK vs 52p — 20-day pass (risk on train, {len(ad)} common days)")
    print("="*88)
    stack([p52], "52p baseline")
    stack([p52, nas_fade], "52p + NAS fade|range")
    stack([p52, jpy_mom], "52p + USDJPY mom|rng+unc")
    stack([p52, nas_fade, jpy_mom], "52p + both regime legs")
    print("-"*88)
    print("Beats 52p only if TEST and foldWorst both rise. Regime routing earns its place if the")
    print("fade-in-range + USDJPY-momentum legs (decorrelated, different days) lift the pass honestly.")


if __name__ == "__main__":
    main()
