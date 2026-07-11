"""
newstrat/exits.py — EXIT-MANAGEMENT LAB (user request): for each 52p leg, sweep the exit grid —
fixed TP at several RR, breakeven at +1R/+2R, scale-outs (50% off at +1R/+2R, rest trails/BE),
and trail-instead-of-TP — engine already models all of these (tp_R / be_R / trail_R / partial_R).

Honesty protocol: the best variant per leg is picked on TRAIN expR only; TEST is reported for
everything; the composed "exit-tuned" build is then MC'd vs baseline with the usual folds. Exit
params are the easiest thing in trading to overfit (many knobs, smooth response), so a variant
only replaces the baseline if it wins on train AND doesn't degrade on test. Run: python3 exits.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3"), ("..", "challengephaseHF")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from search import build_days                            # noqa: E402

COST = 2.0; BREAKER = 2.0; NP = 40000
RISKS = (0.005, 0.006, 0.0075, 0.01)

# leg -> (builder, baseline-name, variants {name: kwargs})
LEGS = {
    "A_USORB": (lambda df, **kw: S.orb(df, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True, **kw),
        "tp4", {
        "tp4":          dict(tp_R=4.0, be_R=0.0),
        "tp4_be1":      dict(tp_R=4.0, be_R=1.0),
        "tp4_be2":      dict(tp_R=4.0, be_R=2.0),
        "tp3":          dict(tp_R=3.0, be_R=0.0),
        "tp6":          dict(tp_R=6.0, be_R=0.0),
        "tp2":          dict(tp_R=2.0, be_R=0.0),
        "trail3":       dict(tp_R=0.0, be_R=0.0, trail_R=3.0),
        "tp4_p50@1R":   dict(tp_R=4.0, be_R=0.0, partial_R=1.0, partial_frac=0.5),
        "tp4_p50@2R":   dict(tp_R=4.0, be_R=0.0, partial_R=2.0, partial_frac=0.5),
        "tp4_be1_p@1R": dict(tp_R=4.0, be_R=1.0, partial_R=1.0, partial_frac=0.5),
    }),
    "B_EUORB": (lambda df, **kw: S.orb(df, open_min=11*60, or_min=30, stop_pts=50, vol_filter=True, **kw),
        "tp4_be1", {
        "tp4_be1":      dict(tp_R=4.0, be_R=1.0),
        "tp4":          dict(tp_R=4.0, be_R=0.0),
        "tp4_be2":      dict(tp_R=4.0, be_R=2.0),
        "tp3_be1":      dict(tp_R=3.0, be_R=1.0),
        "tp6_be1":      dict(tp_R=6.0, be_R=1.0),
        "tp2_be1":      dict(tp_R=2.0, be_R=1.0),
        "tp4_be1_p@1R": dict(tp_R=4.0, be_R=1.0, partial_R=1.0, partial_frac=0.5),
        "trail3_be1":   dict(tp_R=0.0, be_R=1.0, trail_R=3.0),
    }),
    "C_VWPULL": (lambda df, **kw: S.vwap_pullback(df, stop_pts=40, **kw),
        "tp6", {
        "tp6":          dict(tp_R=6.0, trail_R=0.0),
        "tp4":          dict(tp_R=4.0, trail_R=0.0),
        "tp8":          dict(tp_R=8.0, trail_R=0.0),
        "tp3":          dict(tp_R=3.0, trail_R=0.0),
        "tp6_p50@2R":   dict(tp_R=6.0, trail_R=0.0, partial_R=2.0, partial_frac=0.5),
        "tp6_p50@1R":   dict(tp_R=6.0, trail_R=0.0, partial_R=1.0, partial_frac=0.5),
        "trail3":       dict(tp_R=0.0, trail_R=3.0),
    }),
    "D_PDHL": (lambda df, **kw: S.pdh_pdl(df, stop_pts=60, **kw),
        "trail3", {
        "trail3":       dict(trail_R=3.0),
        "trail2":       dict(trail_R=2.0),
        "trail4":       dict(trail_R=4.0),
        "trail5":       dict(trail_R=5.0),
    }),
}


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    folds = np.array_split(ad, 4)
    best = {}
    print("EXIT LAB — per-leg grid, expR train | test  (pick on TRAIN; * = train-best)")
    for leg, (bld, base, variants) in LEGS.items():
        print(f"\n  {leg}  (baseline {base}):")
        scores = {}
        for name, kw in variants.items():
            tr = engine.simulate(df, bld(df, **kw), cost_pts=COST)
            g = tr[tr["day"] <= cut]; gte = tr[tr["day"] > cut]
            etr = engine.edge_stats(g)["expR"]; ete = engine.edge_stats(gte)["expR"]
            wr = engine.edge_stats(tr)["wr"]
            scores[name] = (etr, ete, tr)
            print(f"    {name:14} WR {wr*100:4.1f}%  train {etr:+.3f}  test {ete:+.3f}")
        train_best = max(scores, key=lambda k: scores[k][0])
        # replace baseline only if train-best ALSO doesn't degrade on test vs baseline
        eb_tr, eb_te, _ = scores[base]
        nb_tr, nb_te, _ = scores[train_best]
        keep = train_best if (train_best != base and nb_te >= eb_te - 0.01) else base
        best[leg] = (keep, scores[keep][2])
        print(f"    -> train-best {train_best}{' *ADOPTED*' if keep==train_best and keep!=base else ''}"
              f"{' (kept baseline: test degrades)' if keep==base and train_best!=base else ' (baseline already best)' if train_best==base else ''}")

    # composed build vs baseline 52p
    import ChallengePhase52p as CP52
    base_tr = engine.simulate(df, CP52.build(df), cost_pts=COST)
    tuned_tr = pd.concat([t for _, t in best.values()], ignore_index=True)
    def mc(t, days, r, dl): return ftmo.run_mc(build_days(t[t['day'].isin(set(days))], days, BREAKER), r, dl,
                                               n_paths=NP, seed=11, block=5)
    dtr = ad[ad <= cut]; dte = ad[ad > cut]
    print("\nCOMPOSED (exit-tuned) vs baseline 52p — MC (risk on train):")
    for tag, t in [("52p baseline", base_tr), ("52p exit-tuned", tuned_tr)]:
        r = max(RISKS, key=lambda x: mc(t, dtr, x, 20)["pass_rate"])
        te = mc(t, dte, r, 20)
        fps = [mc(t, f, max(RISKS, key=lambda x: mc(t, np.concatenate([y for y in folds if y[0]!=f[0]]), x, 20)["pass_rate"]), 20)["pass_rate"] for f in folds]
        a40 = mc(t, ad, max(RISKS, key=lambda x: mc(t, dtr, x, 40)["pass_rate"]), 40)
        e = engine.edge_stats(t)
        print(f"  {tag:16} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f} | TE20 {te['pass_rate']*100:4.1f}% "
              f"blow {te['blow_rate']*100:4.1f}% | folds {np.mean(fps)*100:4.1f}/worst {np.min(fps)*100:4.1f}% "
              f"| 40d {a40['pass_rate']*100:4.1f}% blow {a40['blow_rate']*100:4.1f}%")


if __name__ == "__main__":
    main()
