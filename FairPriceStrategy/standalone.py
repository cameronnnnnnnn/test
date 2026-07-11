"""
FairPriceStrategy/standalone.py — turn the fair-price framework into the best STANDALONE FTMO
challenge strategy it can honestly be (not a 52p add-on).

What the v3 analysis established about this framework on NAS100:
  * the +EV core is the BIG-CANDLE trade (trigger candle >25pts -> 50pt stop): +0.05/+0.13
    both halves; small-candle (25/38) trades bleed both halves -> EXCLUDED.
  * P1 opening continuation is the strongest slice (+0.11/+0.18); P2 reversion flips -> tested
    again here per-component, only kept if BOTH halves positive.
  * 1.5R at ~0.5 trades/day cannot reach +10% in a month (17% pass) — so the exit geometry is
    swept ON TRAIN ONLY (the video itself allows "move the take profit / let it play out").

Build steps (all selection on TRAIN, verified on TEST, then MC under full FTMO rules):
  1. candidate legs, all within the framework (session open = unfair flow):
       NY  P1 big-candle continuation  (the proven core)
       NY  P2 big-candle BOS reversion (kept only if train+test both +)
       LDN P1 big-candle continuation  (same logic at the 10:00 London open)
  2. exit sweep per leg on train: fixed 1.52R / 2.5R / 4R / trail(2R after BE@1R)
  3. assemble surviving legs -> MC 20d/40d, risk swept, OOS + 4-fold
Run: python3 standalone.py
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

BIG = 25.0; STOP = 50.0
EXITS = {"rr1.5": dict(tp_R=1.52), "rr2.5": dict(tp_R=2.5), "rr4": dict(tp_R=4.0),
         "trail": dict(tp_R=0.0, be_R=1.0, trail_R=2.0)}


def leg_orders(df, open_min, phase, exit_kw, cont_win=15, rev_end=90, min_room=30.0,
               bos_lookback=45, swing_k=2, wick_max=0.30, max_p1=2, sess_end=22*60+55):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    rng = np.maximum(h - l, 1e-9); body = np.abs(c - o)
    wickr = (rng - body) / rng
    cand_dir = np.sign(c - o)
    orders = []
    spec = ExitSpec(max_bars=rev_end, **exit_kw)
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= open_min) & (t < open_min + rev_end)]
        pre = gi[t < open_min]
        full = gi[(t >= open_min) & (t <= sess_end)]
        if len(sess) < 30 or len(pre) < 5:
            continue
        zone_hi, zone_lo = h[pre[-1]], l[pre[-1]]
        cdir = cand_dir[sess[0]]
        win = np.concatenate([pre[-bos_lookback:], sess])
        swH, swL = fractal_swings(h[win], l[win], swing_k)
        base = len(win) - len(sess)
        eod = full[-1]
        n_p1 = 0
        for j in range(1, len(sess) - 1):
            b = sess[j]; lm = base + j
            mins = tod[b] - open_min
            if phase == 1:
                if mins > cont_win or cdir == 0 or n_p1 >= max_p1:
                    if mins > cont_win: break
                    continue
                d = int(cdir)
            else:
                if mins <= cont_win: continue
                if c[b] > zone_hi:   d = -1
                elif c[b] < zone_lo: d = +1
                else:                continue
                room = (c[b] - zone_hi) if d < 0 else (zone_lo - c[b])
                if room < min_room: continue
            if rng[b] <= BIG:                                   # big-candle filter (the +EV core)
                continue
            disp = (cand_dir[b] == d and rng[b] > rng[b-1] and wickr[b] <= wick_max
                    and ((c[b] > h[b-1]) if d > 0 else (c[b] < l[b-1])))
            bos = False
            if d > 0:
                lv = [h[win[i2]] for i2 in range(max(0, lm-bos_lookback), lm-1)
                      if swH[i2] and (c[win[i2+1:lm]] <= h[win[i2]]).all()]
                bos = bool(lv) and c[b] > min(lv)
            else:
                lv = [l[win[i2]] for i2 in range(max(0, lm-bos_lookback), lm-1)
                      if swL[i2] and (c[win[i2+1:lm]] >= l[win[i2]]).all()]
                bos = bool(lv) and c[b] < max(lv)
            trigger = bos if phase == 2 else (bos or disp)
            if not trigger:
                continue
            orders.append(dict(entry_bar=b, dir=d, stop_pts=STOP, spec=spec,
                               eod_bar=eod, day=day, tag=f"p{phase}"))
            if phase == 1: n_p1 += 1
    return orders


def seq(tr):
    keep = []
    for day, g in tr.groupby("day"):
        g = g.sort_values("entry_dt"); last = None
        for i, r in g.iterrows():
            if last is not None and r["entry_dt"] <= last: continue
            keep.append(i); last = r["exit_dt"]
    return tr.loc[keep]


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    LEGS = {"NY_P1": (16*60+30, 1), "NY_P2rev": (16*60+30, 2), "LDN_P1": (10*60, 1)}

    print("STEP 1+2 — per-leg exit sweep (expR train | test; pick on TRAIN, keep if both +):")
    chosen = {}
    for name, (om, ph) in LEGS.items():
        best = None
        print(f"  {name}:")
        for ex, kw in EXITS.items():
            tr = seq(engine.simulate(df, leg_orders(df, om, ph, kw), cost_pts=2.0))
            g = tr[tr["day"] <= cut]; gte = tr[tr["day"] > cut]
            etr = engine.edge_stats(g)["expR"] if len(g) > 40 else float("nan")
            ete = engine.edge_stats(gte)["expR"] if len(gte) > 20 else float("nan")
            wr = engine.edge_stats(tr)["wr"] if len(tr) else 0
            print(f"    {ex:6} n={len(tr):4d} WR {wr*100:4.1f}%  train {etr:+.3f}  test {ete:+.3f}")
            if etr == etr and (best is None or etr > best[1]):
                best = (ex, etr, ete, tr)
        if best is None:
            print("    -> DROPPED (too few trades)"); continue
        ex, etr, ete, tr = best
        ok = etr > 0.02 and ete > 0.0
        print(f"    -> train-best {ex}: {'KEPT' if ok else 'DROPPED (not + both halves)'}")
        if ok: chosen[name] = tr

    if not chosen:
        print("\nNo leg survives — the framework has no standalone challenge-grade edge."); return
    allt = pd.concat(chosen.values(), ignore_index=True)
    es = engine.edge_stats(allt)
    print(f"\nSTANDALONE BUILD: {'+'.join(chosen)} | {es['n']/len(ad):.2f} trd/day  "
          f"WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}")

    dte = ad[ad > cut]; folds = np.array_split(ad, 4)
    def mc(t, days, r, dl): return ftmo.run_mc(build_days(t[t['day'].isin(set(days))], days, 2.0),
                                               r, dl, n_paths=50000, seed=11, block=5)
    RISKS = (0.0075, 0.01, 0.0125, 0.015, 0.02)
    dtr = ad[ad <= cut]
    r = max(RISKS, key=lambda x: mc(allt, dtr, x, 20)["pass_rate"])
    te = mc(allt, dte, r, 20)
    fps = [mc(allt, f, max(RISKS, key=lambda x: mc(allt, np.concatenate([y for y in folds if y[0]!=f[0]]), x, 20)["pass_rate"]), 20)["pass_rate"] for f in folds]
    print(f"\nFTMO MC (risk on train, r*={r*100:.2f}%):")
    for dl in (20, 40, 60):
        m = mc(allt, ad, r, dl)
        print(f"  {dl}d ALL: pass {m['pass_rate']*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%")
    print(f"  20d OOS: pass {te['pass_rate']*100:.1f}%  blow {te['blow_rate']*100:.1f}%  "
          f"| folds mean {np.mean(fps)*100:.1f}% worst {np.min(fps)*100:.1f}%")
    print("\nContext: 52p 55/72/80 (20/40/60d), 52pPlus 58/75/83.")


if __name__ == "__main__":
    main()
