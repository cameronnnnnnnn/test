"""
news/disp_to_fair.py — the user's displacement-toward-fair idea on the two NAS opens:
price is >= D pts away from the FAIR anchor (night: pre-halt 4:59pm close; day: 9:29 close);
a DISPLACEMENT candle fires TOWARD the anchor (body in that direction, range > both prior
candles, wick fraction <= 0.30, closes beyond the prior candle's extreme); enter next bar in
that direction. TP: at the anchor (variable R) OR fixed 1.5R. SL {25,40}. First trigger per
window, night skips >100pt gaps. Windows: 6-8pm ET / 9:30-11:30 ET. 70/30 split, cost 1.5pt.
Run: python3 disp_to_fair.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402

COST = 1.5; WIN = 120; WICK_MAX = 0.30


def orders(nas, which, D, sl, tp_mode):
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    idx = nas.index.values.astype("datetime64[m]")
    rng = np.maximum(h - l, 1e-9); body = np.abs(c - o)
    wickr = (rng - body) / rng
    cdir = np.sign(c - o)
    out = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        if which == "night":
            pos = gi[t == 60]
            if len(pos) != 1: continue
            b0 = pos[0]
            if b0 == 0: continue
            if int((idx[b0] - idx[b0-1]) / np.timedelta64(1, "m")) < 30: continue
            anchor = c[b0-1]
            if abs(o[b0] - anchor) > 100: continue
            om = 60
        else:
            pos = gi[t == 16*60+30]
            if len(pos) != 1: continue
            b0 = pos[0]; anchor = c[b0-1]; om = 16*60+30
        w = gi[(t > om) & (t <= om + WIN)]
        if len(w) < 60: continue
        eod = w[-1]
        for j in w[2:-2]:
            dist = c[j] - anchor
            if abs(dist) < D: continue
            d = -1 if dist > 0 else +1                        # toward the anchor
            disp = (cdir[j] == d and rng[j] > max(rng[j-1], rng[j-2])
                    and wickr[j] <= WICK_MAX
                    and ((c[j] > h[j-1]) if d > 0 else (c[j] < l[j-1])))
            if not disp: continue
            tp_r = abs(dist) / sl if tp_mode == "anchor" else 1.5
            spec = ExitSpec(tp_R=tp_r, be_R=0.0, trail_R=0.0, max_bars=WIN)
            out.append(dict(entry_bar=int(j), dir=int(d), stop_pts=sl, spec=spec,
                            eod_bar=int(eod), day=day, tag=which))
            break                                             # first trigger only
    return out


def main():
    nas = S.prep(data.load())
    ad = np.array(sorted(nas.groupby("date").indices.keys())); cut = ad[int(len(ad)*0.7)]
    for which, lbl in [("night", "NIGHT 6-8pm ET -> pre-halt close"),
                       ("day", "DAY 9:30-11:30 -> 9:29 close")]:
        print(f"\n=== {lbl} — displacement-toward-fair trigger ===")
        print(f"{'D':>4}{'SL':>5}{'TP':>8} | {'train n/WR/expR':>24} | {'test n/WR/expR':>24}")
        for D in (20.0, 40.0):
            for sl in (25.0, 40.0):
                for tp_mode in ("anchor", "1.5R"):
                    tr = engine.simulate(nas, orders(nas, which, D, sl, tp_mode), cost_pts=COST)
                    g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
                    if len(g) < 40 or len(ge) < 20: continue
                    def fmt(x):
                        e = engine.edge_stats(x)
                        return f"n={e['n']:4d} {e['wr']*100:4.1f}% {e['expR']:+.3f}"
                    both = "  <-- BOTH+" if (g["R"].mean() > 0 and ge["R"].mean() > 0) else ""
                    print(f"{D:4.0f}{sl:5.0f}{tp_mode:>8} | {fmt(g):>24} | {fmt(ge):>24}{both}")


if __name__ == "__main__":
    main()
