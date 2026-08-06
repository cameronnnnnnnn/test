"""
news/wr_opt.py — WIN-RATE-optimized small geometries (user request: 1:1 to 1:1.5 RR, small
stops) for the two validated setups:
  A) 6pm reopen REVERSAL (fade the reopen candle; exit 2:55am ET if no TP/SL; >100pt-gap skip)
  B) 9:30 CONTINUATION (WITH the 9:30 candle at 9:31; tested plain and with the big-candle
     (range>=25pt) filter that carried the FairPrice edge; exit EOD 22:55 server)
Grid: SL {10,15,20,25,30,40,50} x TP {1.0,1.25,1.5}R, cost 1.5pt, 70/30 train/test. WR is the
headline; expR shown because tiny stops pay a fat cost share (1.5pt/15pt = 0.10R per trade).
Pick = max TRAIN WR subject to train expR >= 0; verified on TEST. Run: python3 wr_opt.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402

COST = 1.5
SLS = (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0)
TPS = (1.0, 1.25, 1.5)
OPEN = 16*60 + 30; EOD_DAY = 22*60 + 55


def orders_6pm(nas, F, stop, tp):
    spec = ExitSpec(tp_R=tp, be_R=0.0, trail_R=0.0, max_bars=600)
    return [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=stop, spec=spec,
                 eod_bar=int(r.eod), day=r.day, tag="6pm")
            for _, r in F.iterrows() if r.cdir != 0 and abs(r.gap) <= 100]


def orders_930(nas, stop, tp, big_only):
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    spec = ExitSpec(tp_R=tp, be_R=0.0, trail_R=0.0, max_bars=600)
    out = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        ob = gi[t == OPEN]
        if len(ob) != 1: continue
        b0 = ob[0]
        d = np.sign(c[b0] - o[b0])
        if d == 0: continue
        if big_only and (h[b0] - l[b0]) < 25.0: continue
        eod = gi[(t > OPEN) & (t <= EOD_DAY)]
        if len(eod) < 60: continue
        out.append(dict(entry_bar=int(b0), dir=int(d), stop_pts=stop, spec=spec,
                        eod_bar=int(eod[-1]), day=day, tag="930"))
    return out


def sweep(nas, order_fn, label):
    ad = np.array(sorted(nas.groupby("date").indices.keys())); cut = ad[int(len(ad)*0.7)]
    print(f"\n=== {label} ===")
    print(f"{'SL':>4}{'TP':>7} | {'train WR':>9}{'expR':>8} | {'test WR':>8}{'expR':>8}{'n':>6}")
    best = None
    for s in SLS:
        for tp in TPS:
            tr = engine.simulate(nas, order_fn(s, tp), cost_pts=COST)
            g = tr[tr["day"] <= cut]; ge = tr[tr["day"] > cut]
            if len(g) < 50 or len(ge) < 30: continue
            wtr = (g["R"] > 0).mean(); etr = g["R"].mean()
            wte = (ge["R"] > 0).mean(); ete = ge["R"].mean()
            print(f"{s:4.0f}{tp:6.2f}R | {wtr*100:8.1f}%{etr:+8.3f} | {wte*100:7.1f}%{ete:+8.3f}{len(tr):>6}")
            if etr >= 0 and (best is None or wtr > best[0]):
                best = (wtr, s, tp, wte, ete)
    if best:
        wtr, s, tp, wte, ete = best
        print(f"  -> PICK (max train WR with train expR>=0): SL {s:.0f} / TP {s*tp:.0f} ({tp}R)"
              f"  — TEST: WR {wte*100:.1f}%  expR {ete:+.3f}")
    else:
        print("  -> NO cell has train expR >= 0 at these geometries.")
    return best


def main():
    nas = S.prep(data.load())
    F = build_days(nas)
    sweep(nas, lambda s, tp: orders_6pm(nas, F, s, tp), "6PM REOPEN REVERSAL (small geometries)")
    sweep(nas, lambda s, tp: orders_930(nas, s, tp, True),
          "9:30 CONTINUATION — big candle only (range>=25pt)")
    sweep(nas, lambda s, tp: orders_930(nas, s, tp, False), "9:30 CONTINUATION — every day")


if __name__ == "__main__":
    main()
