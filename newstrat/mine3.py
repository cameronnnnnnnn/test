"""
newstrat/mine3.py — creative mining, iteration 11. Five families on NAS100 (train/test protocol):
  A. OVERNIGHT GAP map: gap-at-US-open vs prior close (ATR units) -> fill probability + session drift.
  B. 2-DAY SEQUENCES: prior two session days' signs (UU/UD/DU/DD) -> next session drift.
  C. SPEED-TO-FIRST-MOVE: minutes for the session to first move 0.25 ATR from open; fast start ->
     trend day? (initiative begets continuation)
  D. PRIOR CLOSE-LOCATION: where yesterday closed in its own range -> today's session drift.
  E. OR-SIZE -> ORB QUALITY: does the 15-min opening range's size (vs ATR) predict whether the
     52p A-leg breakout WORKS? (deployable filter if yes)
Run: python3 mine3.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"),):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                     # noqa: E402

OPEN = 16*60+30; EOD = 22*60+55


def main():
    df = S.prep(data.load())
    atr = S.daily_atr(df, 14)
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    groups = list(df.groupby("date").indices.items())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]

    # per-day session features
    feats = []
    prev = {}
    for k, (day, gi) in enumerate(groups):
        a = atr.get(day, np.nan)
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t <= EOD)]
        if len(sess) < 200 or not (a == a and a > 0):
            prev[day] = None; continue
        op, cl = o[sess[0]], c[sess[-1]]
        hi, lo = h[sess].max(), l[sess].min()
        # speed to first 0.25-ATR move
        disp = np.abs(c[sess] - op)/a
        idx = np.argmax(disp >= 0.25) if (disp >= 0.25).any() else -1
        speed = idx if idx >= 0 else len(sess)
        sessret = (cl - op)/a
        cloc = (cl - lo)/(hi - lo) if hi > lo else 0.5
        pc = c[groups[k-1][1]][-1] if k > 0 else np.nan
        gap = (op - pc)/a if pc == pc else np.nan
        filled = (lo <= pc <= hi) if pc == pc else np.nan
        feats.append(dict(day=day, gap=gap, filled=filled, sessret=sessret, cloc=cloc,
                          speed=speed, drift_after=(cl - op)/a))
    z = pd.DataFrame(feats)
    z["prev_ret"] = z["sessret"].shift(1); z["prev2_ret"] = z["sessret"].shift(2)
    z["prev_cloc"] = z["cloc"].shift(1)
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]

    def cell(g, gte, col, lbl):
        mu = g[col].mean(); t_ = mu/(g[col].std()/np.sqrt(len(g))) if len(g) > 25 else 0
        mute = gte[col].mean() if len(gte) > 12 else np.nan
        sig = " *" if abs(t_) >= 2.5 else ""
        ok = ("HOLDS" if mute == mute and np.sign(mute) == np.sign(mu) else "flips") if abs(t_) >= 2.5 else ""
        print(f"   {lbl:24} n={len(g):4d}  ret_tr={mu:+.4f} t={t_:+.1f}  te={mute:+.4f}  {ok}{sig}")

    print("A. OVERNIGHT GAP (ATR units) -> session drift + fill rate")
    q = tr["gap"].dropna().quantile([0.1, 0.9]).values
    for lbl, m in [("gap-down big (<q10)", z["gap"] < q[0]), ("gap-up big (>q90)", z["gap"] > q[1]),
                   ("small gap (mid 80%)", (z["gap"] >= q[0]) & (z["gap"] <= q[1]))]:
        cell(tr[m[tr.index]], te[m[te.index]], "sessret", lbl)
    big = z[np.abs(z["gap"]) > np.abs(z["gap"]).quantile(0.8)]
    print(f"   gap-fill rate (big gaps): train {big[big['day']<=cut]['filled'].mean()*100:.0f}%  "
          f"test {big[big['day']>cut]['filled'].mean()*100:.0f}%")

    print("\nB. 2-DAY SEQUENCE -> next session drift")
    for s1, s2, lbl in [(1, 1, "UP,UP"), (1, -1, "UP,DN"), (-1, 1, "DN,UP"), (-1, -1, "DN,DN")]:
        m = (np.sign(z["prev2_ret"]) == s1) & (np.sign(z["prev_ret"]) == s2)
        cell(tr[m[tr.index]], te[m[te.index]], "sessret", lbl)

    print("\nC. SPEED to first 0.25-ATR move -> |session move| & signed continuation")
    qs = tr["speed"].quantile([0.25, 0.75]).values
    for lbl, m in [("fast start (<q25 min)", z["speed"] < qs[0]), ("slow start (>q75)", z["speed"] > qs[1])]:
        g = tr[m[tr.index]]; gte = te[m[te.index]]
        mu = g["sessret"].abs().mean(); mute = gte["sessret"].abs().mean()
        print(f"   {lbl:24} n={len(g):4d}  |ret|_tr={mu:.3f}  te={mute:.3f}   (range expansion)")

    print("\nD. PRIOR-DAY CLOSE LOCATION -> today's session drift")
    for lbl, m in [("closed strong (>0.8)", z["prev_cloc"] > 0.8), ("closed weak (<0.2)", z["prev_cloc"] < 0.2)]:
        cell(tr[m[tr.index]], te[m[te.index]], "sessret", lbl)

    print("\nE. OR-SIZE -> 52p A-leg ORB quality (expR by OR-size quintile, train | test)")
    orA = engine.simulate(df, S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0,
                                    be_R=0.0, vol_filter=True), cost_pts=2.0)
    ors = {}
    for day, gi in groups:
        t = tod[gi]; w = gi[(t >= 16*60) & (t < 16*60+15)]
        a = atr.get(day, np.nan)
        if len(w) >= 10 and a == a and a > 0:
            ors[day] = (h[w].max() - l[w].min())/a
    orA["orsz"] = orA["day"].map(ors)
    qq = orA[orA["day"] <= cut]["orsz"].quantile([0.2, 0.4, 0.6, 0.8]).values
    orA["q"] = np.searchsorted(qq, orA["orsz"].fillna(-1))
    for q5 in range(5):
        g = orA[(orA["q"] == q5) & (orA["day"] <= cut)]; gte = orA[(orA["q"] == q5) & (orA["day"] > cut)]
        etr = engine.edge_stats(g)["expR"] if len(g) > 30 else float("nan")
        ete = engine.edge_stats(gte)["expR"] if len(gte) > 15 else float("nan")
        print(f"   OR-size Q{q5+1}: expR {etr:+.3f} (n{len(g)}) | {ete:+.3f} (n{len(gte)})")


if __name__ == "__main__":
    main()
