"""
news/opens_rev.py — does "reverse the opening 1m candle" transfer to OTHER significant opens?
Same rule as the 6pm reopen leg, NO per-session tuning (pure hypothesis transfer): reverse the
direction of the session's first 1m candle, enter next minute, 40pt SL / 120pt TP (3R), flat at
the session-appropriate eod. 70/30 train/test. cost 1.5pt.
Mechanism note: the 6pm edge comes from the post-halt thin-book overshoot; the other opens have
no halt (no gap), so failure here is informative, not surprising.
Run: python3 opens_rev.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402

STOP = 40.0; TP_R = 3.0; COST = 1.5

OPENS = {                                                    # open minute (server) -> eod minute
    "6pm reopen  01:00": (1*60,      9*60+55),
    "Tokyo~9am   02:00": (2*60,      9*60+55),
    "London8am   10:00": (10*60,     15*60+25),
    "midnightET  07:00": (7*60,      15*60+25),
    "8:30ET news 15:30": (15*60+30,  22*60+55),
    "NY 9:30     16:30": (16*60+30,  22*60+55),
}


def main():
    nas = S.prep(data.load())
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    spec = ExitSpec(tp_R=TP_R, be_R=0.0, trail_R=0.0, max_bars=900)
    groups = nas.groupby("date").indices
    print(f"'reverse the open candle' transferred (40/{STOP*TP_R:.0f}, cost {COST}pt, 70/30 split)\n")
    print(f"{'open':22}{'TRAIN':>32}{'TEST':>32}")
    for name, (om, em) in OPENS.items():
        orders = []
        for day, gi in groups.items():
            t = tod[gi]
            pos = gi[t == om]
            if len(pos) != 1: continue
            b0 = pos[0]
            d = -np.sign(c[b0] - o[b0])
            if d == 0: continue
            eod = gi[(t > om) & (t <= em)]
            if len(eod) < 60: continue
            orders.append(dict(entry_bar=int(b0), dir=int(d), stop_pts=STOP, spec=spec,
                               eod_bar=int(eod[-1]), day=day, tag=name))
        if len(orders) < 100:
            print(f"{name:22}{'(too few sessions)':>32}"); continue
        tr = engine.simulate(nas, orders, cost_pts=COST)
        ad = np.array(sorted(tr["day"].unique())); cut = ad[int(len(ad)*0.7)]
        g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
        def fmt(x):
            if len(x) < 30: return "(n<30)"
            e = engine.edge_stats(x)
            return f"n={e['n']:3d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"
        print(f"{name:22}{fmt(g):>32}{fmt(ge):>32}")


if __name__ == "__main__":
    main()
