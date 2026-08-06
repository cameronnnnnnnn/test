"""
news/nyopen_rev.py — the user's 9:30 fade, tested exactly, plus the N-minute generalization.

Signal: after N minutes of the NY session (N=1 -> the 9:30 candle itself, the user's current
trade), fade the cumulative move: close of minute N vs the 9:30 OPEN. Enter next minute.
Geometry grid: 50pt stop x TP {50 (1R), 75 (1.5R), 150 (3R)}. Exit EOD 22:55 server.
N grid: 1,2,3,4,5,10,15. 70/30 train/test, all cells reported, cost 1.5pt.
Run: python3 nyopen_rev.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402

OPEN = 16*60 + 30                                            # 9:30 ET
EOD = 22*60 + 55
STOP = 50.0; COST = 1.5
NS = (1, 2, 3, 4, 5, 10, 15)
TPS = (1.0, 1.5, 3.0)


def main():
    nas = S.prep(data.load())
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    groups = nas.groupby("date").indices
    ad = np.array(sorted(groups.keys())); cut = ad[int(len(ad)*0.7)]

    print(f"NY 9:30 fade — N-minute cumulative move reversed (50pt SL, cost {COST}pt, eod 22:55)\n")
    print(f"{'N':>3}{'TP':>6} | {'TRAIN n/WR/expR':>26} | {'TEST n/WR/expR':>26}")
    for N in NS:
        for tp in TPS:
            spec = ExitSpec(tp_R=tp, be_R=0.0, trail_R=0.0, max_bars=600)
            orders = []
            for day, gi in groups.items():
                t = tod[gi]
                ob = gi[t == OPEN]
                sb = gi[t == OPEN + N - 1]
                if len(ob) != 1 or len(sb) != 1: continue
                d = -np.sign(c[sb[0]] - o[ob[0]])            # fade the first-N-minute move
                if d == 0: continue
                eod = gi[(t > OPEN + N - 1) & (t <= EOD)]
                if len(eod) < 60: continue
                orders.append(dict(entry_bar=int(sb[0]), dir=int(d), stop_pts=STOP, spec=spec,
                                   eod_bar=int(eod[-1]), day=day, tag=f"N{N}"))
            tr = engine.simulate(nas, orders, cost_pts=COST)
            g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
            def fmt(x):
                if len(x) < 30: return "(n<30)"
                e = engine.edge_stats(x)
                return f"n={e['n']:3d} WR {e['wr']*100:4.1f}% {e['expR']:+.3f}"
            print(f"{N:>3}{tp:>5.1f}R | {fmt(g):>26} | {fmt(ge):>26}")
        print()


if __name__ == "__main__":
    main()
