"""
newstrat/daytype.py — loop iteration 7b, MY OWN pattern ideas (user: invent, don't just use mine).
Both aim to predict the DAY TYPE and condition the already-profitable momentum legs:

  A. OVERNIGHT COMPRESSION -> DAY EXPANSION. Mechanism: volatility clustering has a wrinkle —
     a compressed overnight session (tight 00:00-16:25 range vs ATR) often precedes an expanded
     US day (energy builds, then releases at the open). If true, the US-ORB should earn MORE on
     compressed-overnight days -> a day filter for 52p's A-leg.
  B. TREND-DAY EARLY DETECTION. Mechanism: trend days open directional and STAY directional.
     If the first US hour closes near its own extreme (close-location > 0.8 of the hour's range),
     the rest of the day should continue that direction -> a 17:30 continuation entry.

Measured data-first on NAS100 (train quantiles, train t-stats, one-shot test check), then each
promising cell is turned into actual trades and evaluated train/test. Run: python3 daytype.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
for p in (V4,):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                  # noqa: E402
from engine import ExitSpec                            # noqa: E402

OPEN = 16*60+30; EOD = 22*60+55


def main():
    df = S.prep(data.load())
    atr = S.daily_atr(df, 14); df["atr"] = df["date"].map(atr); df = df[df["atr"] == df["atr"]]
    h, l, c, o = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    tod = df["tod"].values
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]

    # ---------- per-day features ----------
    rows = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]; a = df["atr"].values[gi[0]]
        on = gi[(t >= 0) & (t < OPEN - 5)]
        sess = gi[(t >= OPEN) & (t <= EOD)]
        h1 = gi[(t >= OPEN) & (t < OPEN + 60)]
        if len(on) < 200 or len(sess) < 200 or len(h1) < 45 or not (a > 0): continue
        on_rng = (h[on].max() - l[on].min()) / a
        s_rng = (h[sess].max() - l[sess].min()) / a
        r1 = h[h1].max() - l[h1].min()
        cloc = (c[h1[-1]] - l[h1].min()) / r1 if r1 > 0 else 0.5
        dir1 = np.sign(c[h1[-1]] - o[h1[0]])
        cont = dir1 * (c[sess[-1]] - c[h1[-1]]) / a          # continuation after hour 1, ATR units
        rows.append((day, on_rng, s_rng, cloc, dir1, cont))
    z = pd.DataFrame(rows, columns=["day", "on_rng", "s_rng", "cloc", "dir1", "cont"])
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]

    # ---------- A: compression -> expansion ----------
    q = tr["on_rng"].quantile([0.2, 0.4, 0.6, 0.8]).values
    z["oq"] = np.searchsorted(q, z["on_rng"]); tr = z[z["day"] <= cut]; te = z[z["day"] > cut]
    print("A. overnight range quintile -> US session range (ATR units)   [Q1 = most compressed]")
    for qq in range(5):
        g = tr[tr["oq"] == qq]; gte = te[te["oq"] == qq]
        print(f"   Q{qq+1}: on_rng={g['on_rng'].mean():.2f}  sess_rng train={g['s_rng'].mean():.2f} "
              f"test={gte['s_rng'].mean():.2f}  n={len(g)}")
    # does the ORB leg earn more on compressed days? simulate 52p leg A, split by quintile
    orbA = engine.simulate(df, S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0,
                                     be_R=0.0, vol_filter=True), cost_pts=2.0)
    oq_map = dict(zip(z["day"], z["oq"]))
    orbA["oq"] = orbA["day"].map(oq_map)
    print("   US-ORB (52p leg A) expR by overnight-compression quintile (train | test):")
    for qq in range(5):
        g = orbA[(orbA["oq"] == qq) & (orbA["day"] <= cut)]
        gte = orbA[(orbA["oq"] == qq) & (orbA["day"] > cut)]
        etr = engine.edge_stats(g)["expR"] if len(g) > 30 else float("nan")
        ete = engine.edge_stats(gte)["expR"] if len(gte) > 15 else float("nan")
        print(f"   Q{qq+1}: expR {etr:+.3f} (n{len(g)}) | {ete:+.3f} (n{len(gte)})")

    # ---------- B: first-hour close-location -> continuation ----------
    print("\nB. first-hour close-location -> rest-of-day CONTINUATION (dir-signed, ATR units)")
    qb = tr["cloc"].quantile([0.2, 0.4, 0.6, 0.8]).values
    z["cq"] = np.searchsorted(qb, z["cloc"]); tr = z[z["day"] <= cut]; te = z[z["day"] > cut]
    for qq in range(5):
        g = tr[tr["cq"] == qq]; gte = te[te["cq"] == qq]
        mu = g["cont"].mean(); t_ = mu/(g["cont"].std()/np.sqrt(len(g))) if len(g) > 30 else 0
        mute = gte["cont"].mean() if len(gte) > 15 else float("nan")
        mark = " *" if abs(t_) >= 2.5 else ""
        print(f"   Q{qq+1}: cloc={g['cloc'].mean():.2f}  cont train={mu:+.4f} t={t_:+.1f}  test={mute:+.4f}  n={len(g)}{mark}")

    # tradeable version: enter 17:30 in dir1 when cloc extreme (>=0.8 with dir up, <=0.2 with dir dn)
    print("\n   TRADEABLE: 17:30 continuation entry on extreme close-location, 0.5-ATR stop, EOD exit:")
    ext = z[((z["cloc"] >= 0.8) & (z["dir1"] > 0)) | ((z["cloc"] <= 0.2) & (z["dir1"] < 0))]
    orders = []
    gmap = df.groupby("date").indices
    for _, r in ext.iterrows():
        gi = gmap[r["day"]]; t = tod[gi]
        sess = gi[(t >= OPEN + 60) & (t <= EOD)]
        if len(sess) < 30: continue
        a = df["atr"].values[gi[0]]
        spec = ExitSpec(tp_R=0.0, be_R=0.0, trail_R=0.0, max_bars=10**9)
        orders.append(dict(entry_bar=sess[0], dir=int(r["dir1"]), stop_pts=0.5*a, spec=spec,
                           eod_bar=sess[-1], day=r["day"], tag="trendday"))
    trd = engine.simulate(df, orders, cost_pts=2.0)
    for lbl, gsel in [("train", trd[trd["day"] <= cut]), ("test", trd[trd["day"] > cut])]:
        if len(gsel):
            e = engine.edge_stats(gsel)
            print(f"   {lbl}: n={e['n']}  WR {e['wr']*100:.1f}%  expR {e['expR']:+.3f}  PF {e['pf']:.2f}")


if __name__ == "__main__":
    main()
