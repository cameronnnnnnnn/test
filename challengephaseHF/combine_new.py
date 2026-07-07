"""
challengephaseHF/combine_new.py — the payoff test. Two legs survived honest scrutiny:
  * USDJPY Tokyo-range breakout (00-08 server, hard 3R, 0.30-ATR stop) — real but thin edge,
    ~0 correlated with NAS100.
  * NAS100 turn-of-month long — real +0.145R differential over beta, but limited data.
Both are low-frequency / high-RR (the structure that does NOT concentrate daily-cap risk),
and both are ~0 correlated with the NAS100 combo. So they are exactly the kind of leg that
*could* lift the 20-day monthly pass above the NAS100-only ceiling. This tests whether they
actually do, honestly:

  - common server-day axis (NAS100 ∩ USDJPY), all instruments on ONE FTMO account
  - risk chosen on TRAIN(70%), pass reported on TEST(30%)  [no in-sample cherry-pick]
  - 4 contiguous CV folds -> mean and WORST-fold pass (regime robustness)
  - daily-return correlation matrix (confirm the legs really are decorrelated)

Compare 52p-alone vs +USDJPY vs +tom vs +both. Run: python3 combine_new.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import fx_data, ChallengePhase52p as CP52            # noqa: E402
from asian_break import asian_break, fx_cost         # noqa: E402
from creative import tom_long                         # noqa: E402

DEADLINE = 20; BREAKER = 2.0
RISKS = (0.005, 0.0075, 0.01, 0.0125, 0.015)


def day_series(trades, ad):
    return np.asarray(build_days(trades, ad, BREAKER)["day_R"], float)


def best_risk(days, n=30000):
    br = (-1, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, DEADLINE, n_paths=n, seed=11, block=5)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r)
    return br[1]


def mc_at(days, r, n=60000):
    return ftmo.run_mc(days, r, DEADLINE, n_paths=n, seed=11, block=5)


def main():
    print("Loading NAS100 (52p) + USDJPY Tokyo-breakout + NAS tom_long ...")
    nas = S.prep(data.load())
    nas_tr = engine.simulate(nas, CP52.build(nas), cost_pts=2.0)
    tom_tr = engine.simulate(nas, tom_long(nas), cost_pts=2.0)

    dj = S.prep(fx_data.load("USDJPY"))
    atr = S.daily_atr(dj, n=14); sm = {d: 0.30 * v for d, v in atr.items() if v == v}
    jpy_tr = engine.simulate(dj, asian_break(dj, 0, 8*60, sm, tp_R=3.0), cost_pts=fx_cost(dj))

    # common server-day axis
    ad = np.array(sorted(set(nas["date"].unique()).intersection(set(dj["date"].unique()))))
    def clip(tr): return tr[tr["day"].isin(set(ad))]
    nas_tr, tom_tr, jpy_tr = clip(nas_tr), clip(tom_tr), clip(jpy_tr)
    print(f"common days: {len(ad)}  ({pd.Timestamp(ad[0]).date()} .. {pd.Timestamp(ad[-1]).date()})\n")

    legs = {"52p": nas_tr, "USDJPY": jpy_tr, "tom": tom_tr}
    print("per-leg edge over common days:")
    for k, tr in legs.items():
        e = engine.edge_stats(tr) if len(tr) else dict(n=0, wr=0, expR=0, pf=0)
        print(f"  {k:8} n={e['n']:5d}  {e['n']/len(ad):4.2f}/day  WR {e['wr']*100:4.1f}%  "
              f"expR {e['expR']:+.3f}  PF {e['pf']:.2f}")

    # correlation of daily R
    dser = {k: day_series(tr, ad) for k, tr in legs.items()}
    DR = pd.DataFrame(dser, index=ad)
    print("\ndaily-return correlation:")
    print("          " + "".join(f"{c:>9}" for c in legs))
    for c in legs:
        print(f"  {c:8}" + "".join(f"{DR.corr().loc[c,d]:9.2f}" for d in legs))

    # ---- combos: risk on TRAIN(70%), pass on TEST(30%); plus 4-fold mean/worst ----
    cut = ad[int(len(ad)*0.7)]; tr_days = ad[ad <= cut]; te_days = ad[ad > cut]
    folds = np.array_split(ad, 4)

    def combo_days(keys, days):
        tr = pd.concat([legs[k][legs[k]["day"].isin(set(days))] for k in keys], ignore_index=True)
        return build_days(tr, days, BREAKER)

    def evaluate(keys, tag):
        r = best_risk(combo_days(keys, tr_days))
        te = mc_at(combo_days(keys, te_days), r)
        allm = mc_at(combo_days(keys, ad), r)
        fps = []
        for f in folds:
            r_f = best_risk(combo_days(keys, np.concatenate([x for x in folds if not (x[0]==f[0])])))
            fps.append(mc_at(combo_days(keys, f), r_f)["pass_rate"])
        print(f"  {tag:22} r*={r*100:4.2f}%  ALL {allm['pass_rate']*100:4.1f}%  "
              f"TEST {te['pass_rate']*100:4.1f}%  blow {te['blow_rate']*100:4.1f}%  "
              f"| folds mean {np.mean(fps)*100:4.1f}% worst {np.min(fps)*100:4.1f}%")

    print("\n" + "="*82)
    print("MONTHLY (20-day) PASS — risk picked on train, reported on test + 4-fold CV")
    print("="*82)
    evaluate(["52p"], "52p alone (NAS100)")
    evaluate(["52p", "USDJPY"], "52p + USDJPY Tokyo")
    evaluate(["52p", "tom"], "52p + tom (NAS seasonal)")
    evaluate(["52p", "USDJPY", "tom"], "52p + USDJPY + tom")
    print("-"*82)
    print("Beats the 52p-alone baseline only if TEST and (especially) WORST-FOLD pass rise")
    print("materially. A higher ALL-data number with a flat/worse worst-fold = in-sample luck.")


if __name__ == "__main__":
    main()
