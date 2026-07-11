"""
newstrat/mine4.py — VWAP pattern mining (iteration 12). Three families on NAS100:

  A. FIRST-TOUCH TIMING: from 17:00, how long until price first touches the session VWAP?
     Never/late touch = one-sided trend day. Measure rest-of-day continuation (signed by which
     side of VWAP price was on at 17:00) for early/late/never buckets.
  B. CROSS-COUNT CHOP GAUGE: # of VWAP crosses 16:30-17:30 (live chop measure) -> (i) rest-of-day
     |range|, (ii) the C+D runner legs' expR gated by it (deployable if it splits them).
  C. OPEN vs PRIOR VALUE: open's distance from YESTERDAY's session VWAP (ATR units) -> session
     drift (auction theory: open outside value -> directional day).

Train-only selection, one-shot test check. Run: python3 mine4.py
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
    h, l, c, o = df["high"].values, df["low"].values, df["close"].values, df["open"].values
    v = df["tickvol"].values.astype(float)
    tp = (h + l + c)/3.0
    tod = df["tod"].values
    groups = list(df.groupby("date").indices.items())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]

    rows = []; prior_vwap = {}
    prev_day = None
    for day, gi in groups:
        a = atr.get(day, np.nan)
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t <= EOD)]
        if len(sess) < 250 or not (a == a and a > 0):
            prev_day = day; continue
        pv = np.cumsum(tp[sess]*v[sess]); vv = np.cumsum(v[sess]) + 1e-9
        vwap = pv/vv
        prior_vwap[day] = vwap[-1]
        ts = tod[sess]
        # A: first touch after 17:00
        j0 = np.argmax(ts >= 17*60)
        side = np.sign(c[sess[j0]] - vwap[j0])
        touch = -1
        for j in range(j0, len(sess)):
            if (side > 0 and l[sess[j]] <= vwap[j]) or (side < 0 and h[sess[j]] >= vwap[j]):
                touch = ts[j] - 17*60; break
        cont = side * (c[sess[-1]] - c[sess[j0]])/a
        # B: crosses in first hour
        w1 = (ts >= OPEN) & (ts <= OPEN+60)
        dev = c[sess] - vwap
        sgn = np.sign(dev[w1])
        crosses = int(np.sum(np.abs(np.diff(sgn)) > 1))
        srange = (h[sess].max() - l[sess].min())/a
        # C: open vs prior vwap
        pvw = prior_vwap.get(prev_day, np.nan)
        odist = (o[sess[0]] - pvw)/a if pvw == pvw else np.nan
        sessret = (c[sess[-1]] - o[sess[0]])/a
        rows.append(dict(day=day, touch=touch, cont=cont, crosses=crosses, srange=srange,
                         odist=odist, sessret=sessret))
        prev_day = day
    z = pd.DataFrame(rows)
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]

    def cell(g, gte, col, lbl):
        if len(g) < 25: return
        mu = g[col].mean(); t_ = mu/(g[col].std()/np.sqrt(len(g)))
        mute = gte[col].mean() if len(gte) > 12 else np.nan
        sig = " *" if abs(t_) >= 2.5 else ""
        ok = ("HOLDS" if mute == mute and np.sign(mute) == np.sign(mu) else "flips") if abs(t_) >= 2.5 else ""
        print(f"   {lbl:26} n={len(g):4d}  {col}_tr={mu:+.4f} t={t_:+.1f}  te={mute:+.4f}  {ok}{sig}")

    print("A. FIRST-VWAP-TOUCH timing (from 17:00) -> signed continuation to close")
    for lbl, m in [("touch <30m (balanced)", (z["touch"] >= 0) & (z["touch"] < 30)),
                   ("touch 30-120m", (z["touch"] >= 30) & (z["touch"] < 120)),
                   ("late/never (>120m)", (z["touch"] >= 120) | (z["touch"] < 0))]:
        cell(tr[m[tr.index]], te[m[te.index]], "cont", lbl)

    print("\nB. VWAP crosses 16:30-17:30 -> day character + runner-leg gate")
    q = tr["crosses"].quantile([0.33, 0.67]).values
    for lbl, m in [("few crosses (1-sided)", z["crosses"] <= q[0]), ("many crosses (choppy)", z["crosses"] >= q[1])]:
        g = tr[m[tr.index]]; gte = te[m[te.index]]
        print(f"   {lbl:26} n={len(g):4d}  range_tr={g['srange'].mean():.3f}  te={gte['srange'].mean():.3f}")
    # runner legs gated by cross-count (few = trend hint), causal: legs enter after 17:30
    CD = pd.concat([engine.simulate(df, S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0), cost_pts=2.0),
                    engine.simulate(df, S.pdh_pdl(df, stop_pts=60, trail_R=3.0), cost_pts=2.0)], ignore_index=True)
    cmap = dict(zip(z["day"], z["crosses"]))
    CD["cr"] = CD["day"].map(cmap)
    for lbl, m in [("C+D few-cross days", CD["cr"] <= q[0]), ("C+D many-cross days", CD["cr"] >= q[1])]:
        g = CD[m & (CD["day"] <= cut)]; gte = CD[m & (CD["day"] > cut)]
        etr = engine.edge_stats(g)["expR"] if len(g) > 30 else float("nan")
        ete = engine.edge_stats(gte)["expR"] if len(gte) > 15 else float("nan")
        print(f"   {lbl:26} expR train {etr:+.3f} (n{len(g)}) | test {ete:+.3f} (n{len(gte)})")

    print("\nC. OPEN vs PRIOR-DAY VWAP (value) -> session drift")
    qo = tr["odist"].dropna().quantile([0.15, 0.85]).values
    for lbl, m in [("open far BELOW value", z["odist"] < qo[0]), ("open far ABOVE value", z["odist"] > qo[1]),
                   ("open inside value", (z["odist"] >= qo[0]) & (z["odist"] <= qo[1]))]:
        cell(tr[m[tr.index]], te[m[te.index]], "sessret", lbl)


if __name__ == "__main__":
    main()
