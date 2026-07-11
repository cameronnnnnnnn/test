"""
newstrat/events.py — EVENT-CAUSALITY mining (loop iteration 7). User brief: find repetitive moves
and what CAUSES them — sweeps of daily/session highs/lows, equilibrium/mean-reversion, price-time
structure. Two scans, data-first (measure distributions, don't test templates):

  1. SWEEP CAUSALITY — event = first touch of PDH/PDL or overnight H/L (+0.02 ATR buffer).
     Classify within 10 bars: RECLAIMED (closed back inside) vs ACCEPTED (still beyond).
     Measure forward 30m/60m return FROM THE CLASSIFICATION BAR (the tradeable moment), in ATR
     units, split by AM/PM. -> does a reclaim actually predict reversal? does acceptance continue?

  2. EQUILIBRIUM — displacement of close from session VWAP in ATR units, sampled every 30 min
     (non-overlapping-ish, avoids autocorrelation-inflated t-stats). Forward 30m return by
     displacement quintile (quantiles from TRAIN). Reversion = stretched quintiles drift back.

Selection on TRAIN (|t|>=3.0 here; fewer tests than mine.py), one-shot sign-check on TEST,
drift always compared to round-turn cost. Run: python3 events.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, fx_data                 # noqa: E402

INSTR = {"NAS100": (16*60+30, 2.0), "GER40": (10*60, 1.5), "USDJPY": (10*60, None)}
BUF = 0.02      # sweep buffer in ATR
HOLD = 10       # bars to classify reclaim vs accept
TCRIT = 3.0


def load(x):
    df = S.prep(data.load()) if x == "NAS100" else S.prep(fx_data.load(x))
    atr = S.daily_atr(df, n=14)
    df["atr"] = df["date"].map(atr)
    return df[df["atr"] == df["atr"]]


def rt_cost(x, df):
    if x == "NAS100": return 2.0
    px = df["close"].iloc[-1]
    pt = 0.001 if px > 50 else 0.00001
    return 1.5 * df["spread"].median() * pt


def sweep_scan(df, cut, cost):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values; dates = df["date"].values
    groups = list(df.groupby("date").indices.items())
    dayHL = {d: (h[gi].max(), l[gi].min()) for d, gi in groups}
    rows = []
    for k in range(1, len(groups)):
        day, gi = groups[k]
        a = df["atr"].values[gi[0]]
        if not (a > 0): continue
        pdh, pdl = dayHL[groups[k-1][0]]
        t = tod[gi]
        # overnight range = 00:00 -> 09:55 server
        on = gi[(t >= 0) & (t < 10*60 - 5)]
        onH, onL = (h[on].max(), l[on].min()) if len(on) > 30 else (np.nan, np.nan)
        for lvl, side, name in [(pdh, +1, "PDH"), (pdl, -1, "PDL"), (onH, +1, "ONH"), (onL, -1, "ONL")]:
            if not (lvl == lvl): continue
            sess = gi[(t >= 10*60) & (t <= 22*60)]
            if len(sess) < 60: continue
            # first touch beyond level+buffer
            if side > 0:
                hits = sess[h[sess] >= lvl + BUF*a]
            else:
                hits = sess[l[sess] <= lvl - BUF*a]
            if not len(hits): continue
            e = hits[0]
            # classification bar: e+HOLD (or reclaim moment if earlier)
            fut = sess[sess > e][:HOLD]
            if len(fut) < HOLD: continue
            if side > 0:
                rec_idx = next((j for j, b in enumerate(fut) if c[b] < lvl), None)
            else:
                rec_idx = next((j for j, b in enumerate(fut) if c[b] > lvl), None)
            cls = "REC" if rec_idx is not None else "ACC"
            cb = fut[rec_idx] if rec_idx is not None else fut[-1]
            # forward returns from classification bar close
            after = sess[sess > cb]
            if len(after) < 60: continue
            f30 = (c[after[29]] - c[cb]) / a
            f60 = (c[after[59]] - c[cb]) / a
            ampm = "AM" if tod[e] < 16*60 else "PM"
            rows.append((day, name, side, cls, ampm, f30, f60))
    z = pd.DataFrame(rows, columns=["day", "lvl", "side", "cls", "ampm", "f30", "f60"])
    out = []
    for (lvl, cls, ampm), g in z.groupby(["lvl", "cls", "ampm"]):
        tr = g[g["day"] <= cut]; te = g[g["day"] > cut]
        if len(tr) < 120: continue
        for hz in ("f30", "f60"):
            mu = tr[hz].mean(); sd = tr[hz].std(); n = len(tr)
            t_ = mu / (sd/np.sqrt(n))
            if abs(t_) >= TCRIT:
                mute = te[hz].mean() if len(te) > 40 else np.nan
                out.append((lvl, cls, ampm, hz, n, mu, t_, mute))
    return out, z


def equil_scan(df, cut, open_min):
    h, l, c, v = df["high"].values, df["low"].values, df["close"].values, df["tickvol"].values.astype(float)
    tp = (h + l + c) / 3.0
    tod = df["tod"].values
    rows = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        sess = gi[(t >= open_min) & (t <= 22*60+30)]
        if len(sess) < 120: continue
        a = df["atr"].values[gi[0]]
        if not (a > 0): continue
        pv = np.cumsum(tp[sess]*v[sess]); vv = np.cumsum(v[sess]) + 1e-9
        vwap = pv/vv
        ts = tod[sess]
        for j in range(30, len(sess)-30):
            if ts[j] % 30 != 0: continue          # sample on the half-hour only
            disp = (c[sess[j]] - vwap[j]) / a
            f30 = (c[sess[j+30]] - c[sess[j]]) / a
            rows.append((day, disp, f30))
    z = pd.DataFrame(rows, columns=["day", "disp", "f30"])
    tr = z[z["day"] <= cut]; te = z[z["day"] > cut]
    q = tr["disp"].quantile([0.1, 0.3, 0.7, 0.9]).values
    def b(v_): return np.searchsorted(q, v_)
    tr["q"] = tr["disp"].map(b); te["q"] = te["disp"].map(b)
    res = []
    for qq in range(5):
        g = tr[tr["q"] == qq]; gte = te[te["q"] == qq]
        if len(g) < 200: continue
        mu = g["f30"].mean(); t_ = mu/(g["f30"].std()/np.sqrt(len(g)))
        res.append((qq, len(g), g["disp"].mean(), mu, t_, gte["f30"].mean() if len(gte) > 60 else np.nan))
    return res


def main():
    for x, (om, _) in INSTR.items():
        df = load(x); ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
        cost = rt_cost(x, df); med_atr = np.nanmedian(df["atr"].values)
        cost_atr = cost/med_atr
        print("="*86)
        print(f"{x}   (round-turn cost = {cost_atr:.4f} ATR)")
        out, z = sweep_scan(df, cut, cost)
        print("  1. SWEEP CAUSALITY (fwd from classification bar, ATR units; |t|>=3 on train):")
        if out:
            for lvl, cls, ampm, hz, n, mu, t_, mute in out:
                ok = "HOLDS" if (mute == mute and np.sign(mute) == np.sign(mu)) else ("?" if mute != mute else "flips")
                edge = "" if abs(mu) < 1.5*cost_atr else "  [>1.5x cost]"
                print(f"     {lvl} {cls} {ampm} {hz}: n={n:4d}  mu={mu:+.4f}  t={t_:+.1f}  test={mute:+.4f} -> {ok}{edge}")
        else:
            print("     nothing passes |t|>=3 on train")
        # base rates for context
        tr = z[z["day"] <= cut]
        rr = tr.groupby("cls")["f30"].agg(["mean", "count"])
        print(f"     (base: REC n={int(rr.loc['REC','count']) if 'REC' in rr.index else 0} "
              f"mu={rr.loc['REC','mean'] if 'REC' in rr.index else float('nan'):+.4f} | "
              f"ACC n={int(rr.loc['ACC','count']) if 'ACC' in rr.index else 0} "
              f"mu={rr.loc['ACC','mean'] if 'ACC' in rr.index else float('nan'):+.4f})")
        print("  2. EQUILIBRIUM (fwd 30m by VWAP-displacement quintile; reversion = opposite sign):")
        for qq, n, dmean, mu, t_, mute in equil_scan(df, cut, om):
            sig = " *" if abs(t_) >= TCRIT else ""
            ok = "" if abs(t_) < TCRIT else ("  HOLDS" if (mute == mute and np.sign(mute) == np.sign(mu)) else "  flips")
            print(f"     Q{qq+1} disp={dmean:+.2f}ATR  n={n:5d}  fwd30={mu:+.4f}  t={t_:+.1f}  test={mute:+.4f}{sig}{ok}")
        print()


if __name__ == "__main__":
    main()
