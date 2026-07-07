"""
challengephaseHF/hf2_search.py — cross-validated combo search over the positive-EV, high-RR,
low-frequency legs. 4 contiguous time folds, rank by WORST fold (robust). Finds the best
2-4 leg uncorrelated combo and whether it beats the ~44-47% ceiling. Run: python3 hf2_search.py
"""
import os, sys, itertools
import numpy as np, pandas as pd
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import hf_strats as HF                               # noqa: E402
import warnings; warnings.filterwarnings("ignore")

df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique())); COST = 2.0
# only the positive-EV high-RR legs (drop DRIVE, MIM which were negative)
SET = {
 "US1630": S.orb(df, open_min=16*60+30, or_min=30, stop_pts=60, tp_R=4.0, be_R=1.0, vol_filter=True),
 "US1600": S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True),
 "EU1100": S.orb(df, open_min=11*60, or_min=30, stop_pts=50, tp_R=4.0, be_R=1.0, vol_filter=True),
 "ASIA":   S.orb(df, open_min=3*60, or_min=30, stop_pts=40, tp_R=4.0, be_R=1.0, vol_filter=True),
 "VWP6":   S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0),
 "PDHL":   S.pdh_pdl(df, stop_pts=60, trail_R=3.0),
 "IB60":   S.ib_break(df, ib_min=60, stop_pts=60, trail_R=3.0),
 "GAP3":   HF.gaprev(df, gap_pts=15, stop_pts=50, tp_R=3.0),
}
TR = {nm: engine.simulate(df, o, COST) for nm, o in SET.items()}
K = 4; n = len(ad); FOLDS = [ad[i*n//K:(i+1)*n//K] for i in range(K)]
RISKS = (0.0075, 0.01, 0.0125, 0.015)


def kfold(combo, breaker=2.0):
    tr = pd.concat([TR[c] for c in combo], ignore_index=True)
    best = None
    for r in RISKS:
        ps = []
        for fd in FOLDS:
            d = build_days(tr[tr["day"].isin(set(fd))], fd, breaker)
            ps.append(ftmo.run_mc(d, r, 20, n_paths=25000, seed=11, block=5)["pass_rate"])
        ps = np.array(ps)
        if best is None or ps.min() > best[0]: best = (ps.min(), ps.mean(), ps, r)
    return best


rows = []
for k in (3, 4):
    for combo in itertools.combinations(SET, k):
        mn, me, ps, r = kfold(combo)
        rows.append((combo, mn, me, ps, r))
rows.sort(key=lambda x: x[1], reverse=True)
print("=" * 92)
print(f"BEST HIGH-RR UNCORRELATED COMBOS — {K}-fold 20-day pass, ranked by WORST fold")
print("=" * 92)
print(f"  {'combo':30} {'risk':>6} {'minFold':>8} {'meanFold':>9}   per-fold")
for combo, mn, me, ps, r in rows[:12]:
    cs = "+".join(combo)
    print(f"  {cs:30} {r*100:5.2f}% {mn*100:7.1f}% {me*100:8.1f}%   [{' '.join(f'{x*100:4.1f}' for x in ps)}]")
print("-" * 92)
b = rows[0]
print(f"BEST: {'+'.join(b[0])}  worst-fold {b[1]*100:.1f}%  mean-fold {b[2]*100:.1f}%  risk {b[4]*100:.2f}%")
print(f"vs the established ~44-47% ceiling and the 0EV-optimal ~38.6%. Does it break through?")
