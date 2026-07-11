"""
newstrat/stack.py — iteration 9: THE GRAND UNIFICATION. Five keepers survived the whole research
program, each individually worth ~+1pt on 52p. They've never been tested TOGETHER. Are the lifts
additive (real decorrelated edges should be), or do they overlap/collide?

  K1 fade|range     NAS100 mean-reversion, only on prior-day-range days (55% WR, +0.11/+0.20)
  K2 usdjpy_tokyo   USDJPY 00-08 range breakout, 3R, 0.30-ATR stop (+0.06/+0.11)
  K3 ger40_close    GER40 long 18:00->18:45 into the DAX cash close (+0.03/+0.07)
  K4 tom            NAS100 turn-of-month long (last day + first 3), trail 3R (+0.15/+0.36)
  K5 monday         NAS100 long through the Monday US session, 0.5-ATR stop, EOD (+0.10/+0.14 ATR)

Eval on the NAS∩GER∩JPY common-day axis: leg edges + correlation matrix, then MC 20d & 40d pass
(risk picked on TRAIN, TEST reported, 4-fold mean/worst) for 52p alone, each +keeper, and the full
stack. Run: python3 stack.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo, fx_data     # noqa: E402
from engine import ExitSpec                               # noqa: E402
from search import build_days                             # noqa: E402
import ChallengePhase52p as CP52                           # noqa: E402
from asian_break import asian_break                        # noqa: E402
from creative import tom_long                              # noqa: E402
from regime_matrix import regime_map                       # noqa: E402
from mined import time_leg                                 # noqa: E402

BREAKER = 2.0; NP = 50000
RISKS = (0.005, 0.006, 0.0075, 0.01)


def monday_leg(df, sm):
    tod = df["tod"].values
    orders = []
    spec = ExitSpec(tp_R=0.0, be_R=0.0, trail_R=0.0, max_bars=10**9)
    for day, gi in df.groupby("date").indices.items():
        if pd.Timestamp(day).dayofweek != 0: continue
        t = tod[gi]
        sess = gi[(t >= 16*60+30) & (t <= 22*60+55)]
        stp = sm.get(day, np.nan)
        if len(sess) < 100 or not (stp == stp): continue
        orders.append(dict(entry_bar=sess[0], dir=1, stop_pts=stp, spec=spec,
                           eod_bar=sess[-1], day=day, tag="monday"))
    return orders


def main():
    nas = S.prep(data.load()); ger = S.prep(fx_data.load("GER40")); jpy = S.prep(fx_data.load("USDJPY"))
    aN = S.daily_atr(nas, 14); aG = S.daily_atr(ger, 14); aJ = S.daily_atr(jpy, 14)
    smN20 = {d: 0.20*v for d, v in aN.items() if v == v}
    smN50 = {d: 0.50*v for d, v in aN.items() if v == v}
    smG25 = {d: 0.25*v for d, v in aG.items() if v == v}
    smJ30 = {d: 0.30*v for d, v in aJ.items() if v == v}
    jc = 1.5 * jpy["spread"].median() * 0.001

    rng_days = set(d for d in nas["date"].unique() if regime_map(nas).get(d) == "range")
    legs = {
        "52p":     engine.simulate(nas, CP52.build(nas), cost_pts=2.0),
        "K1_fade": engine.simulate(nas, S.vwap_fade_sel(nas, k=2.0, open_min=16*60, trail_R=2.0,
                                   partial_R=1.0, stop_map=smN20), cost_pts=2.0),
        "K2_jpy":  engine.simulate(jpy, asian_break(jpy, 0, 8*60, smJ30, tp_R=3.0), cost_pts=jc),
        "K3_ger":  engine.simulate(ger, time_leg(ger, +1, 18*60, 18*60+45, smG25, "G2"), cost_pts=1.5),
        "K4_tom":  engine.simulate(nas, tom_long(nas), cost_pts=2.0),
        "K5_mon":  engine.simulate(nas, monday_leg(nas, smN50), cost_pts=2.0),
    }
    legs["K1_fade"] = legs["K1_fade"][legs["K1_fade"]["day"].isin(rng_days)]

    ad = np.array(sorted(set(nas["date"].unique()) & set(ger["date"].unique()) & set(jpy["date"].unique())))
    for k in legs: legs[k] = legs[k][legs[k]["day"].isin(set(ad))]
    cut = ad[int(len(ad)*0.7)]; dtr = ad[ad <= cut]; dte = ad[ad > cut]
    folds = np.array_split(ad, 4)
    print(f"common days: {len(ad)}   legs:")
    for k, t in legs.items():
        e = engine.edge_stats(t) if len(t) else dict(n=0, wr=0, expR=0)
        print(f"  {k:8} n={e['n']:5d} {e['n']/len(ad):5.2f}/d  WR {e['wr']*100:4.1f}%  expR {e['expR']:+.3f}")

    D = pd.DataFrame({k: np.asarray(build_days(t, ad, BREAKER)["day_R"], float) for k, t in legs.items()}, index=ad)
    print("\ncorrelation of daily R:")
    ks = list(legs)
    print("        " + "".join(f"{k[:7]:>9}" for k in ks))
    for k in ks:
        print(f"  {k:7}" + "".join(f"{D.corr().loc[k,k2]:9.2f}" for k2 in ks))

    def mc(t, days, r, dl): return ftmo.run_mc(build_days(t[t['day'].isin(set(days))], days, BREAKER),
                                               r, dl, n_paths=NP, seed=11, block=5)
    def evalstack(keys, tag):
        t = pd.concat([legs[k] for k in keys], ignore_index=True)
        r20 = max(RISKS, key=lambda r: mc(t, dtr, r, 20)["pass_rate"])
        te20 = mc(t, dte, r20, 20)
        fps = [mc(t, f, max(RISKS, key=lambda r: mc(t, np.concatenate([x for x in folds if x[0]!=f[0]]), r, 20)["pass_rate"]), 20)["pass_rate"] for f in folds]
        r40 = max(RISKS, key=lambda r: mc(t, dtr, r, 40)["pass_rate"])
        a40 = mc(t, ad, r40, 40)
        print(f"  {tag:22} TE20 {te20['pass_rate']*100:4.1f}% blow {te20['blow_rate']*100:4.1f}% "
              f"| folds {np.mean(fps)*100:4.1f}%/worst {np.min(fps)*100:4.1f}% "
              f"| 40d(all) {a40['pass_rate']*100:4.1f}% blow {a40['blow_rate']*100:4.1f}%")

    print("\nMC pass (risk on train; TE 20d + folds + all-data 40d):")
    evalstack(["52p"], "52p alone")
    for k in ["K1_fade", "K2_jpy", "K3_ger", "K4_tom", "K5_mon"]:
        evalstack(["52p", k], f"52p + {k}")
    evalstack(["52p", "K1_fade", "K3_ger", "K4_tom", "K5_mon"], "52p + NAS/GER keepers")
    evalstack(list(legs), "FULL STACK (all 6)")


if __name__ == "__main__":
    main()
