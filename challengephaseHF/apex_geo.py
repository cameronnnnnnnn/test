"""
challengephaseHF/apex_geo.py — re-optimize the reopen-reversal EXIT GEOMETRY for the APEX 100K
intraday-trailing objective (pass rate / speed), not raw expR. Hypothesis: under an intraday
trail, unrealized MFE ratchets the floor without banking anything, so closer TPs (or BE stops)
should beat the expR-optimal 40/3R.

Grid: SL {25,30,40,50} x exits {1R..4R fixed, 3R+BE@1R, trail(2R after BE@1R)}; per cell the
risk {400,560,800} is chosen on TRAIN pass%; winner verified on TEST nights. Apex 100K rules:
+$6,000 target, $3,000 INTRADAY trail, 50% consistency (soft), no min days. cost 1.5pt.
Run: python3 apex_geo.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "news")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402
from fast_pass import mc_times                              # noqa: E402

START = 100_000; TGT = 6000; DD = 3000
RISKS = (400, 560, 800)
SLS = (25.0, 30.0, 40.0, 50.0)
EXITS = {"1R": dict(tp_R=1.0), "1.5R": dict(tp_R=1.5), "2R": dict(tp_R=2.0),
         "2.5R": dict(tp_R=2.5), "3R": dict(tp_R=3.0), "4R": dict(tp_R=4.0),
         "3R+BE1": dict(tp_R=3.0, be_R=1.0), "trail": dict(tp_R=0.0, be_R=1.0, trail_R=2.0)}


def tri_for(nas, F, stop, exit_kw, cost=1.5):
    spec = ExitSpec(max_bars=600, **exit_kw)
    orders = [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=stop, spec=spec,
                   eod_bar=int(r.eod), day=r.day, tag="rev")
              for _, r in F.iterrows() if r.cdir != 0]
    tr = engine.simulate(nas, orders, cost_pts=cost).sort_values("entry_dt")
    return tr


def main():
    nas = S.prep(data.load())
    F = build_days(nas)
    ad = np.array(sorted(F["day"].unique())); cut = ad[int(len(ad)*0.7)]
    print(f"APEX 100K geometry re-optimization (pass% within 120 nights; risk picked on TRAIN)\n")
    print(f"{'':8}" + "".join(f"{e:>9}" for e in EXITS))
    best = (-1, None)
    cells = {}
    for s in SLS:
        row = f"  SL{s:3.0f} "
        for ename, ekw in EXITS.items():
            tr = tri_for(nas, F, s, ekw)
            tri_tr = tr[tr["day"] <= cut][["R", "mae_R", "mfe_R"]].values
            pb = -1; rb = None
            for r in RISKS:
                tp_, bl = mc_times(tri_tr, r, START, TGT, DD, "intraday", 0, 0.50, 1,
                                   n_paths=20_000, deadline=120)
                p = (tp_ <= 120).mean()
                if p > pb: pb, rb = p, r
            cells[(s, ename)] = (pb, rb, tr)
            row += f"{pb*100:8.1f} "
            if pb > best[0]: best = (pb, (s, ename))
        print(row)
    (s, ename) = best[1]
    pb, rb, tr = cells[(s, ename)]
    print(f"\nTRAIN-BEST: SL {s:.0f} / {ename} @ ${rb}   train pass {pb*100:.1f}%")
    for lbl, part in [("TEST ", tr[tr["day"] > cut]), ("ALL  ", tr)]:
        tri = part[["R", "mae_R", "mfe_R"]].values
        tp_, bl = mc_times(tri, rb, START, TGT, DD, "intraday", 0, 0.50, 1,
                           n_paths=60_000, deadline=120)
        passed = tp_ <= 120
        med = np.median(tp_[passed]) if passed.any() else float("nan")
        print(f"  {lbl}: pass {passed.mean()*100:5.1f}%  P<=10n {(tp_<=10).mean()*100:4.1f}%  "
              f"P<=20n {(tp_<=20).mean()*100:4.1f}%  med {med:.0f}n  blow {bl.mean()*100:.1f}%")
    # reference: the old 40/3R at its best risk, TEST
    trref = cells[(40.0, "3R")][2]
    tri = trref[trref["day"] > cut][["R", "mae_R", "mfe_R"]].values
    pbest = -1
    for r in RISKS:
        tp_, bl = mc_times(tri, r, START, TGT, DD, "intraday", 0, 0.50, 1, n_paths=60_000, deadline=120)
        p = (tp_ <= 120).mean()
        if p > pbest: pbest, keep = p, (r, tp_, bl)
    r, tp_, bl = keep
    print(f"  [ref 40/3R @ ${r} TEST]: pass {pbest*100:.1f}%  P<=20n {(tp_<=20).mean()*100:.1f}%  "
          f"blow {bl.mean()*100:.1f}%")


if __name__ == "__main__":
    main()
