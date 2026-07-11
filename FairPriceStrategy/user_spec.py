"""
FairPriceStrategy/user_spec.py — the strategy EXACTLY as the user trades it manually (their
correction of my earlier builds). NY 9:30 only.

  P1 CONTINUATION (0-10 min): 0-1 trade. Direction = opening candle. Trigger = significant
     displacement or break-of-structure+close in that direction.
  P2 REVERSION (10-90 min): 2-3 trades. Direction = toward the FAIR AREA (pre-open candle's
     range). Trigger = significant displacement or BOS+close toward fair. TWO NEW RULES:
       * ROOM: only take it if the TP (fixed distance) is NOT more than 5pts past the FURTHEST
         edge of the fair area — i.e. the target must essentially fit within the area (+5).
       * BREAKEVEN: if the TP lies past the CLOSEST edge of the area (target inside/through the
         zone), move SL to breakeven when price first touches that closest edge (beyond it is
         random).
  RISK: 25pt stop / 38pt TP; if the trigger candle is >25pts -> 50/76 at half size (video 2's
     adaptive rule, same $ risk). Sequential (no overlap), max 1 P1 + 3 P2 per day.

Reported honestly: freq, WR (incl. scratch rate), expR train/test, and the FTMO MC.
Run: python3 user_spec.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from engine import ExitSpec                              # noqa: E402
from search import build_days                            # noqa: E402
from fairprice import fractal_swings                     # noqa: E402

CFG = dict(
    stop_small=25.0, stop_big=50.0, big_thresh=25.0, rr=1.52,
    tp_overshoot=5.0,                  # TP may exceed the FAR edge of the fair area by <= this
    cont_win=10, rev_end=90,
    wick_max=0.30, disp_mult=1.0, swing_k=2, bos_lookback=45,
    max_p1=1, max_p2=3, cost_pts=2.0,
)
OPEN = 16*60 + 30


def orders_user(df, cfg=CFG):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    rng = np.maximum(h - l, 1e-9); body = np.abs(c - o)
    wickr = (rng - body) / rng
    cdirs = np.sign(c - o)
    out = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t < OPEN + cfg["rev_end"])]
        pre = gi[t < OPEN]
        if len(sess) < 30 or len(pre) < 5:
            continue
        zhi, zlo = h[pre[-1]], l[pre[-1]]                 # fair area = pre-open candle range
        cdir = cdirs[sess[0]]
        win = np.concatenate([pre[-cfg["bos_lookback"]:], sess])
        swH, swL = fractal_swings(h[win], l[win], cfg["swing_k"])
        base = len(win) - len(sess)
        for j in range(1, len(sess) - 1):
            b = sess[j]; lm = base + j
            mins = tod[b] - OPEN
            phase = 1 if mins <= cfg["cont_win"] else 2
            if phase == 1:
                if cdir == 0: continue
                d = int(cdir)
            else:
                if c[b] > zhi:   d = -1
                elif c[b] < zlo: d = +1
                else:            continue                  # inside the fair area: no trade
            # triggers (either)
            disp = (cdirs[b] == d and rng[b] > cfg["disp_mult"]*rng[b-1]
                    and wickr[b] <= cfg["wick_max"]
                    and ((c[b] > h[b-1]) if d > 0 else (c[b] < l[b-1])))
            bos = False
            if d > 0:
                lv = [h[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                      if swH[i2] and (c[win[i2+1:lm]] <= h[win[i2]]).all()]
                bos = bool(lv) and c[b] > min(lv)
            else:
                lv = [l[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                      if swL[i2] and (c[win[i2+1:lm]] >= l[win[i2]]).all()]
                bos = bool(lv) and c[b] < max(lv)
            if not (disp or bos):
                continue
            stop = cfg["stop_small"] if rng[b] <= cfg["big_thresh"] else cfg["stop_big"]
            tp_d = cfg["rr"] * stop
            be_R = 0.0
            if phase == 2:
                entry_est = c[b]                            # fills next bar open ~ trigger close
                if d < 0:   # short from above the area: near edge zhi, far edge zlo
                    tp_px = entry_est - tp_d
                    if tp_px < zlo - cfg["tp_overshoot"]:   # ROOM rule: TP too far past area
                        continue
                    if tp_px < zhi:                         # TP past the closest edge -> BE rule
                        be_R = max(0.05, (entry_est - zhi) / stop)
                else:
                    tp_px = entry_est + tp_d
                    if tp_px > zhi + cfg["tp_overshoot"]:
                        continue
                    if tp_px > zlo:
                        be_R = max(0.05, (zlo - entry_est) / stop)
            spec = ExitSpec(tp_R=cfg["rr"], be_R=be_R, trail_R=0.0, max_bars=cfg["rev_end"])
            out.append(dict(entry_bar=b, dir=d, stop_pts=stop, spec=spec,
                            eod_bar=sess[-1], day=day, tag=f"P{phase}|s{stop:.0f}"))
    return out


def seq(tr, cfg=CFG):
    tr = tr.copy()
    tr["phase"] = tr["tag"].str.split("|").str[0]
    keep = []
    for day, g in tr.groupby("day"):
        g = g.sort_values("entry_dt")
        last = None; n1 = 0; n2 = 0
        for i, r in g.iterrows():
            if last is not None and r["entry_dt"] <= last: continue
            if r["phase"] == "P1" and n1 >= cfg["max_p1"]: continue
            if r["phase"] == "P2" and n2 >= cfg["max_p2"]: continue
            keep.append(i); last = r["exit_dt"]
            if r["phase"] == "P1": n1 += 1
            else: n2 += 1
    return tr.loc[keep]


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    tr = seq(engine.simulate(df, orders_user(df), cost_pts=CFG["cost_pts"]))
    tr["phase"] = tr["tag"].str.split("|").str[0]
    scr = ((tr["R"] > -0.2) & (tr["R"] < 0.2)).mean()
    print(f"USER SPEC — {len(tr)} trades, {len(tr)/len(ad):.2f}/day "
          f"(scratch rate {scr*100:.0f}% — the BE rule at work)\n")
    def es(g):
        if len(g) < 20: return "(n<20)"
        e = engine.edge_stats(g)
        return f"n={e['n']:4d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"
    print(f"{'':12}{'TRAIN':>36}{'TEST':>36}")
    for v in ["P1", "P2"]:
        g = tr[tr["phase"] == v]
        print(f"  {v:8} {es(g[g['day']<=cut]):>36} {es(g[g['day']>cut]):>36}")
    print(f"  {'ALL':8} {es(tr[tr['day']<=cut]):>36} {es(tr[tr['day']>cut]):>36}")

    dte = ad[ad > cut]
    print("\nFTMO MC:")
    for lbl, dd in [("ALL", build_days(tr, ad, 2.0)),
                    ("OOS", build_days(tr[tr["day"].isin(set(dte))], dte, 2.0))]:
        best = (-1, None, None)
        for r in (0.005, 0.0075, 0.01, 0.0125, 0.015):
            m = ftmo.run_mc(dd, r, 20, n_paths=40000, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        m40 = ftmo.run_mc(dd, r, 40, n_paths=40000, seed=11, block=5)
        print(f"  [{lbl}] 20d pass {p*100:4.1f}% blow {m['blow_rate']*100:4.1f}% (r*={r*100:.2f}%)  40d {m40['pass_rate']*100:.1f}%")


if __name__ == "__main__":
    main()
