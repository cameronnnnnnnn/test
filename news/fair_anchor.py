"""
news/fair_anchor.py — the user's fair-price-anchor idea on NAS100: use the PRE-HALT close
(4:59pm ET, last bar before the 6pm reopen) and the 9:29 close as FAIR anchors; for the 2 hours
after each open, when price has stretched >= D points away from the anchor, trade TOWARD it.
TP = the anchor itself (variable R = stretch/SL), SL fixed, flat at window end. First trigger
per window, night leg skips >100pt reopen gaps. Grid D x SL, 70/30 train/test, cost 1.5pt.
Run: python3 fair_anchor.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402

COST = 1.5
DS = (20.0, 30.0, 40.0, 60.0)
SLS = (25.0, 40.0)
WIN = 120                                                    # 2 hours


def anchor_orders(nas, which, D, sl):
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    idx = nas.index.values.astype("datetime64[m]")
    out = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        if which == "night":
            pos = gi[t == 60]
            if len(pos) != 1: continue
            b0 = pos[0]
            if b0 == 0: continue
            gap_min = int((idx[b0] - idx[b0-1]) / np.timedelta64(1, "m"))
            if gap_min < 30: continue
            anchor = c[b0-1]                                  # pre-halt close (4:59pm ET)
            if abs(o[b0] - anchor) > 100: continue            # monster-gap skip
            om = 60
        else:
            pos = gi[t == 16*60+30]
            if len(pos) != 1: continue
            b0 = pos[0]
            anchor = c[b0-1]                                  # 9:29 close
            om = 16*60+30
        w = gi[(t > om) & (t <= om + WIN)]
        if len(w) < 60: continue
        eod = w[-1]
        for j in w[:-2]:
            dist = c[j] - anchor
            if abs(dist) < D: continue
            d = -1 if dist > 0 else +1                        # toward the anchor
            tp_r = abs(dist) / sl
            spec = ExitSpec(tp_R=tp_r, be_R=0.0, trail_R=0.0, max_bars=WIN)
            out.append(dict(entry_bar=int(j), dir=int(d), stop_pts=sl, spec=spec,
                            eod_bar=int(eod), day=day, tag=f"{which}"))
            break                                             # first trigger only
    return out


def main():
    nas = S.prep(data.load())
    ad = np.array(sorted(nas.groupby("date").indices.keys())); cut = ad[int(len(ad)*0.7)]
    for which, lbl in [("night", "NIGHT — fade to pre-halt close, 6-8pm ET"),
                       ("day", "DAY — fade to 9:29 close, 9:30-11:30 ET")]:
        print(f"\n=== {lbl} ===")
        print(f"{'D':>4}{'SL':>5} | {'train n/WR/expR':>24} | {'test n/WR/expR':>24}")
        for D in DS:
            for sl in SLS:
                tr = engine.simulate(nas, anchor_orders(nas, which, D, sl), cost_pts=COST)
                g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
                if len(g) < 50 or len(ge) < 20: continue
                def fmt(x):
                    e = engine.edge_stats(x)
                    return f"n={e['n']:4d} {e['wr']*100:4.1f}% {e['expR']:+.3f}"
                both = "  <-- BOTH+" if (g["R"].mean() > 0 and ge["R"].mean() > 0) else ""
                print(f"{D:4.0f}{sl:5.0f} | {fmt(g):>24} | {fmt(ge):>24}{both}")


if __name__ == "__main__":
    main()
