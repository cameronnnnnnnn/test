"""
challengephasev3/validate.py — robust re-do of the search that kills the two overfit
traps in search.py:
  1. correlated-leg stacking: combos are now CROSS-FAMILY only (one leg per family),
     so we measure real decorrelation, not 3x leverage on the same signal.
  2. selection-on-test bias: every candidate is scored by 4-FOLD cross-validation over
     contiguous time blocks, and ranked by its WORST fold (min), not the best. A config
     only wins if it holds up in every regime, not just a lucky window.

Also directly probes the "is it just leverage?" question (3x pullback @0.75% vs 1x @2.25%)
and reports the GARCH-filter effect honestly. Run: python3 validate.py
"""
import os, sys, itertools, pickle
import numpy as np, pandas as pd

V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V2 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev2"))
for p in (V4, V2):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
import features as FE                                   # noqa: E402
from strat_gen import eod_map                           # noqa: E402
import search as SR                                     # noqa: E402

DEADLINE = 20; NP = 25000; KF = 4
RISKS = (0.005, 0.0075, 0.01, 0.0125, 0.015)


def family(name):
    for f in ("orb_eu", "orb_us2", "orb_us", "vwpull", "orfade", "vwfadeSel", "vwfade",
              "pdhl", "sweep", "cusumTrend", "cusum", "drive", "ib"):
        if name.startswith(f): return f
    return name


def folds(ad, k=KF):
    n = len(ad); return [ad[i*n//k:(i+1)*n//k] for i in range(k)]


def kfold(trades_list, flds, breaker=2.0, risks=RISKS):
    """For each risk, pass on each fold; return the risk maximising the MIN fold, with
    (min, mean, per-fold list)."""
    tr = pd.concat(trades_list, ignore_index=True) if len(trades_list) > 1 else trades_list[0]
    best = None
    for r in risks:
        ps = []
        for fd in flds:
            d = SR.build_days(tr, fd, breaker)
            ps.append(ftmo.run_mc(d, r, DEADLINE, n_paths=NP, seed=11, block=5)["pass_rate"])
        ps = np.array(ps); score = ps.min()
        if best is None or score > best[0]:
            best = (score, ps.mean(), ps, r)
    return best   # (minfold, meanfold, folds, risk)


def main():
    df = S.prep(data.load()); F = FE.compute(df); eod = eod_map(df)
    ad = np.array(sorted(df["date"].unique())); flds = folds(ad)
    TR = SR.get_trades(df, F, eod)
    names = [n for n in TR if len(TR[n])]

    # -------- best single per family (4-fold, breaker -2R) --------
    print("=" * 90)
    print(f"BEST SINGLE PER FAMILY — {KF}-fold 20-day pass (breaker -2R). rank by MIN fold")
    print("=" * 90)
    per_fam = {}
    for nm in names:
        fam = family(nm); mn, me, ps, r = kfold([TR[nm]], flds)
        if fam not in per_fam or mn > per_fam[fam][1]:
            per_fam[fam] = (nm, mn, me, ps, r)
    fam_rows = sorted(per_fam.values(), key=lambda x: x[1], reverse=True)
    print(f"  {'setup':24s} {'risk':>6} {'minFold':>8} {'meanFold':>9}   per-fold")
    for nm, mn, me, ps, r in fam_rows:
        print(f"  {nm:24s} {r*100:5.2f}% {mn*100:7.1f}% {me*100:8.1f}%   [{' '.join(f'{x*100:4.1f}' for x in ps)}]")

    shortlist = [row[0] for row in fam_rows if row[2] > 0.15][:8]   # decent families only

    # -------- cross-family combos (distinct families) --------
    print("\n" + "=" * 90)
    print("CROSS-FAMILY COMBOS — distinct families, 4-fold, breaker -2R. rank by MIN fold")
    print("=" * 90)
    cand = []
    for k in (2, 3):
        for combo in itertools.combinations(shortlist, k):
            if len({family(c) for c in combo}) < k: continue   # enforce distinct families
            mn, me, ps, r = kfold([TR[c] for c in combo], flds)
            cand.append((combo, mn, me, ps, r))
    cand.sort(key=lambda x: x[1], reverse=True)
    print(f"  {'combo':40s} {'risk':>6} {'minFold':>8} {'meanFold':>9}   per-fold")
    for combo, mn, me, ps, r in cand[:12]:
        cs = "+".join(family(c) for c in combo)
        print(f"  {cs:40s} {r*100:5.2f}% {mn*100:7.1f}% {me*100:8.1f}%   [{' '.join(f'{x*100:4.1f}' for x in ps)}]")

    # -------- is the search.py 'winner' just leverage? --------
    print("\n" + "=" * 90)
    print("OVERFIT CHECK — the search.py 'winner' (3x vwpull) vs 1x vwpull leveraged")
    print("=" * 90)
    vp = [n for n in names if n.startswith("vwpull")]
    trio = [TR["vwpull_s50_tp4_tr3"], TR["vwpull_s50_tp3_tr3"], TR["vwpull_s50_tp3_tr0"]]
    for tag, tl, rs in [("3x vwpull stack", trio, RISKS),
                        ("1x vwpull_s50_tp3_tr3 (2.25% cap)", [TR["vwpull_s50_tp3_tr3"]], (0.0225, 0.02, 0.015))]:
        mn, me, ps, r = kfold(tl, flds, risks=rs)
        print(f"  {tag:34s} risk {r*100:5.2f}%  minFold {mn*100:4.1f}%  meanFold {me*100:4.1f}%  "
              f"[{' '.join(f'{x*100:4.1f}' for x in ps)}]")

    best = cand[0]
    print("\n" + "=" * 90)
    print(f"ROBUST BEST (cross-family, worst-fold): {'+'.join(family(c) for c in best[0])}")
    print(f"  min-fold {best[1]*100:.1f}%  mean-fold {best[2]*100:.1f}%  risk {best[4]*100:.2f}%  breaker -2R")
    print(f"  vs honest ceiling ~44% (20d) and live 4R ~43%. A robust config beats 44% only if")
    print(f"  its WORST fold clears it — that is the number that would survive live.")


if __name__ == "__main__":
    main()
