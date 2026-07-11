"""
newstrat/mine2.py — pattern-mining iteration 10. Two families, mechanism-first:

  A. DISPLACEMENT -> CLOSE momentum. At checkpoints through the US session, bucket the day's
     displacement-from-open (ATR units, train quantiles) and measure the remaining move to the
     close. Positive in the extreme buckets = intraday momentum (documented: Gao et al. first-30m
     -> last-30m); negative = late-day mean reversion. This maps WHERE in the day continuation
     actually lives on NAS100/GER40.

  B. ROUND-NUMBER MAGNETISM (NAS100). At each 30-min sample, distance to the nearest 500-multiple
     (ATR units); response = signed fwd 30m move TOWARD the level. Magnet = positive when close;
     rejection = negative after touches. Mechanism: strike/stop clustering at round levels.

Protocol: train-only selection (|t|>=2.5 flagged, small n honesty), one-shot test sign-check,
drift vs cost. Run: python3 mine2.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephaseHF")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, fx_data                   # noqa: E402

OPEN = 16*60+30; EOD = 22*60+55
CHECKS = [17*60+30, 18*60+30, 19*60+30, 20*60+30, 21*60+30]


def dispmap(df, x, open_min, eod_min):
    atr = S.daily_atr(df, 14)
    c, o = df["close"].values, df["open"].values
    tod = df["tod"].values
    rows = []
    for day, gi in df.groupby("date").indices.items():
        a = atr.get(day, np.nan)
        if not (a == a and a > 0): continue
        t = tod[gi]
        sess = gi[(t >= open_min) & (t <= eod_min)]
        if len(sess) < 200: continue
        op = o[sess[0]]; cl = c[sess[-1]]
        for T in CHECKS:
            w = gi[(t >= open_min) & (t <= T)]
            if len(w) < 30: continue
            ct = c[w[-1]]
            rows.append((day, T, (ct - op)/a, (cl - ct)/a))
    z = pd.DataFrame(rows, columns=["day", "T", "disp", "rem"])
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    print(f"\n{x}: displacement-from-open -> remaining-move-to-close (ATR units)")
    print(f"  {'chk':>6} {'bucket':>10} {'n':>5} {'rem_tr':>8} {'t':>6} {'rem_te':>8}  verdict")
    for T in CHECKS:
        g = z[z["T"] == T]; gtr = g[g["day"] <= cut]; gte = g[g["day"] > cut]
        if len(gtr) < 200: continue
        q = gtr["disp"].quantile([0.2, 0.8]).values
        for name, lo, hi in [("bottom20%", -np.inf, q[0]), ("top20%", q[1], np.inf)]:
            a_ = gtr[(gtr["disp"] > lo) & (gtr["disp"] <= hi)]
            b_ = gte[(gte["disp"] > lo) & (gte["disp"] <= hi)]
            mu = a_["rem"].mean(); t_ = mu/(a_["rem"].std()/np.sqrt(len(a_))) if len(a_) > 30 else 0
            mute = b_["rem"].mean() if len(b_) > 20 else np.nan
            # for momentum: bottom bucket should be NEGATIVE rem, top POSITIVE
            sig = " *" if abs(t_) >= 2.5 else ""
            ok = ("HOLDS" if (mute == mute and np.sign(mute) == np.sign(mu)) else "flips") if abs(t_) >= 2.5 else ""
            hh, mm = T//60, T % 60
            print(f"  {hh:02d}:{mm:02d} {name:>10} {len(a_):5d} {mu:+8.4f} {t_:+6.1f} {mute:+8.4f}  {ok}{sig}")


def roundnum(df):
    atr = S.daily_atr(df, 14)
    c = df["close"].values; tod = df["tod"].values
    rows = []
    for day, gi in df.groupby("date").indices.items():
        a = atr.get(day, np.nan)
        if not (a == a and a > 0): continue
        t = tod[gi]
        sess = gi[(t >= OPEN) & (t <= 22*60)]
        for j in sess:
            if tod[j] % 30 != 0: continue
            px = c[j]
            mod = px % 500.0
            lvl = px - mod if mod < 250 else px + (500 - mod)
            dist = (lvl - px)/a                       # signed: + means level above
            if j + 30 < len(c) and df["date"].values[j+30] == day:
                fwd = (c[j+30] - px)/a
                toward = np.sign(dist)*fwd if dist != 0 else 0.0
                rows.append((day, abs(dist), toward))
    z = pd.DataFrame(rows, columns=["day", "adist", "toward"])
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]
    print("\nNAS100 round-number (500-multiple) magnetism: fwd-30m move TOWARD the level, by distance")
    q = tr["adist"].quantile([0.25, 0.5, 0.75]).values
    edges = [0, q[0], q[1], q[2], np.inf]
    for i in range(4):
        g = tr[(tr["adist"] > edges[i]) & (tr["adist"] <= edges[i+1])]
        gte = te[(te["adist"] > edges[i]) & (te["adist"] <= edges[i+1])]
        mu = g["toward"].mean(); t_ = mu/(g["toward"].std()/np.sqrt(len(g)))
        mute = gte["toward"].mean() if len(gte) > 100 else np.nan
        sig = " *" if abs(t_) >= 2.5 else ""
        print(f"  dist {edges[i]:.2f}-{min(edges[i+1],9):.2f} ATR: n={len(g):5d}  toward_tr={mu:+.4f} t={t_:+.1f}  te={mute:+.4f}{sig}")


def main():
    nas = S.prep(data.load())
    dispmap(nas, "NAS100", OPEN, EOD)
    ger = S.prep(fx_data.load("GER40"))
    dispmap(ger, "GER40", 10*60, 22*60+30)
    roundnum(nas)


if __name__ == "__main__":
    main()
