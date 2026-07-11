"""
newstrat/mine.py — DATA-FIRST edge mining (user brief: don't test known strategies; analyse the
data, find patterns, THEN create a strategy). Instruments: NAS100, GER40, EURUSD, GBPUSD, AUDUSD,
USDJPY. Anti-overfit protocol:
  * all pattern SELECTION happens on TRAIN days (first 70%) only
  * ~90 buckets x 6 instruments x several scans = hundreds of tests -> require |t| >= 3.5
    (Bonferroni-ish) AND prefer coherent runs of adjacent buckets, not lone spikes
  * each surviving pattern is sign-checked ONCE on TEST (last 30%). No iterating on test.

Scans:
  A. time-of-day DRIFT: mean forward 15-min return (in daily-ATR units) per 15-min bucket.
     -> "at HH:MM price tends to drift up/down" = a time-of-day seasonal.
  B. OPEN REACTION: first-5-min move at the NY open (16:30) and EU open (10:00), bucketed into
     quintiles -> mean return over the following hour. Continuation (momentum) vs reversal (MR).
  C. HOUR-to-HOUR autocorrelation by hour: ret(h) vs ret(h+1) — where intraday MR/momentum lives.

Run: python3 mine.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, fx_data                 # noqa: E402

INSTR = ["NAS100", "GER40", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]
TCRIT = 3.5           # selection threshold on TRAIN (multiple-testing corrected)
FWD = 15              # forward horizon (minutes) for the drift scan


def load(x):
    df = S.prep(data.load()) if x == "NAS100" else S.prep(fx_data.load(x))
    atr = S.daily_atr(df, n=14)
    df["atr"] = df["date"].map(atr)
    return df[df["atr"] == df["atr"]]


def cost_frac(x, df):
    """round-turn cost as a fraction of price (for honest 'drift vs cost' comparison)."""
    px = df["close"].iloc[-1]
    if x == "NAS100": return 2.0 / px
    pt = 0.001 if px > 50 else 0.00001
    return 1.5 * df["spread"].median() * pt / px


def split_days(df, f=0.7):
    ad = np.array(sorted(df["date"].unique())); c = ad[int(len(ad)*f)]
    return c


def scanA(df, cut, cost_f):
    """time-of-day drift: fwd 15m return / (ATR/price), per 15-min bucket, train t-stats."""
    c = df["close"].values
    fwd = np.full(len(df), np.nan)
    fwd[:-FWD] = c[FWD:] / c[:-FWD] - 1.0
    same = np.zeros(len(df), bool)
    same[:-FWD] = (df["date"].values[FWD:] == df["date"].values[:-FWD])
    atr_f = (df["atr"] / df["close"]).values
    r = np.where(same, fwd / atr_f, np.nan)
    tod_b = (df["tod"].values // 15)
    train = df["date"].values <= cut
    out = []
    for b in range(0, 96):
        m = train & (tod_b == b) & np.isfinite(r)
        n = m.sum()
        if n < 300: continue
        mu, sd = r[m].mean(), r[m].std()
        t = mu / (sd / np.sqrt(n))
        if abs(t) >= TCRIT:
            # one-shot test check
            mt = (~train) & (tod_b == b) & np.isfinite(r)
            mu_te = r[mt].mean() if mt.sum() > 50 else np.nan
            # drift in cost multiples: mu * ATRfrac(median) / cost
            med_atrf = np.nanmedian(atr_f)
            cost_mult = (abs(mu) * med_atrf) / cost_f if cost_f > 0 else np.nan
            out.append((b, n, mu, t, mu_te, cost_mult))
    return out


def scanB(df, cut, open_min, label):
    """open reaction: first-5-min signed move (ATR units) quintiles -> next-60m mean return."""
    rows = []
    for day, gi in df.groupby("date").indices.items():
        t = df["tod"].values[gi]
        w0 = gi[(t >= open_min) & (t < open_min + 5)]
        w1 = gi[(t >= open_min + 5) & (t < open_min + 65)]
        if len(w0) < 3 or len(w1) < 30: continue
        o = df["open"].values[w0[0]]; c0 = df["close"].values[w0[-1]]; c1 = df["close"].values[w1[-1]]
        a = df["atr"].values[gi[0]]
        if not (a > 0): continue
        rows.append((day, (c0 - o) / a, (c1 - c0) / a))
    z = pd.DataFrame(rows, columns=["day", "r0", "r1"])
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]
    if len(tr) < 200: return None
    q = tr["r0"].quantile([0.2, 0.4, 0.6, 0.8]).values
    def bucket(v): return np.searchsorted(q, v)
    tr["q"] = tr["r0"].map(bucket); te["q"] = te["r0"].map(bucket)
    res = []
    for qq in range(5):
        g = tr[tr["q"] == qq]["r1"]; gte = te[te["q"] == qq]["r1"]
        t = g.mean() / (g.std() / np.sqrt(len(g))) if len(g) > 30 else 0
        res.append((qq, len(g), g.mean(), t, gte.mean() if len(gte) > 20 else np.nan))
    return label, res


def scanC(df, cut):
    """ret(h) vs ret(h+1) correlation by hour, train; flag |t|>=TCRIT."""
    g = df.groupby(["date", df["tod"] // 60])["close"].agg(["first", "last"])
    g["r"] = g["last"] / g["first"] - 1
    piv = g["r"].unstack()          # rows=date, cols=hour
    train = piv.index <= cut
    out = []
    for h in range(0, 23):
        if h not in piv.columns or (h+1) not in piv.columns: continue
        a = piv.loc[train, h]; b = piv.loc[train, h+1]
        m = a.notna() & b.notna()
        n = m.sum()
        if n < 300: continue
        rho = np.corrcoef(a[m], b[m])[0, 1]
        t = rho * np.sqrt((n - 2) / (1 - rho**2))
        if abs(t) >= TCRIT:
            a2 = piv.loc[~train, h]; b2 = piv.loc[~train, h+1]
            m2 = a2.notna() & b2.notna()
            rho_te = np.corrcoef(a2[m2], b2[m2])[0, 1] if m2.sum() > 50 else np.nan
            out.append((h, n, rho, t, rho_te))
    return out


def main():
    for x in INSTR:
        df = load(x); cut = split_days(df); cf = cost_frac(x, df)
        print("=" * 88)
        print(f"{x}  (cost {cf*1e4:.1f} bp of price)   [selection on TRAIN, |t|>={TCRIT}; TEST = one-shot sign check]")
        A = scanA(df, cut, cf)
        if A:
            print("  A. time-of-day drift (fwd 15m, ATR units):")
            for b, n, mu, t, mute, cm in A:
                hh, mm = (b*15)//60, (b*15) % 60
                ok = "HOLDS" if (mute == mute and np.sign(mute) == np.sign(mu)) else ("?" if mute != mute else "flips")
                print(f"     {hh:02d}:{mm:02d}  n={n:5d}  mu={mu:+.4f}ATR  t={t:+5.1f}  test={mute:+.4f}  "
                      f"|drift|={cm:.2f}x cost  -> {ok}")
        else:
            print("  A. no time-of-day bucket passes |t|>=3.5 on train")
        for om, lab in [(16*60+30, "NY 16:30"), (10*60, "EU 10:00")]:
            B = scanB(df, cut, om, lab)
            if B:
                lab2, res = B
                sig = [r for r in res if abs(r[3]) >= 2.5]
                if sig:
                    print(f"  B. open reaction {lab2} (quintile of first-5m move -> next 60m, ATR units):")
                    for qq, n, mu, t, mute in res:
                        mark = " *" if abs(t) >= 2.5 else ""
                        print(f"     Q{qq+1}  n={n:4d}  next60m={mu:+.4f}  t={t:+4.1f}  test={mute:+.4f}{mark}")
        C = scanC(df, cut)
        if C:
            print("  C. hour->next-hour autocorr (train):")
            for h, n, rho, t, rte in C:
                ok = "HOLDS" if (rte == rte and np.sign(rte) == np.sign(rho)) else "flips"
                print(f"     {h:02d}h->{h+1:02d}h  n={n}  rho={rho:+.3f}  t={t:+5.1f}  test_rho={rte:+.3f}  -> {ok}")
        print()


if __name__ == "__main__":
    main()
