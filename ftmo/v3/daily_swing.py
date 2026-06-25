"""
v3/daily_swing.py — multi-day SWING simulator on NAS100 daily bars, producing the
per-day (day_R, day_min_R) series the trusted ftmo.run_mc consumes (block-bootstrap,
since swing daily returns autocorrelate). This correctly models overnight holds vs
the 3% daily cap: day_R = daily mark-to-market change in R; day_min_R = worst intraday
floating from the prior close (the day's low while in a position).

No look-ahead: signals use data through the PRIOR close; entries fill at today's open.
"""
import numpy as np, pandas as pd, data, ftmo

def daily_ohlc(df):
    g = df.groupby("date").agg(o=("open","first"), h=("high","max"),
                               l=("low","min"), c=("close","last"))
    return g.index.values, g["o"].values, g["h"].values, g["l"].values, g["c"].values

def _atr(h, l, c, n=14):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h-l, np.maximum(np.abs(h-pc), np.abs(l-pc)))
    return pd.Series(tr).rolling(n, min_periods=3).mean().values

def swing(df, kind="trend", sma_n=20, atr_mult=3.0, don_n=20, long_only=True):
    """Return per-day arrays day_R, day_min_R, traded for a swing strategy."""
    dates, O, H, L, C = daily_ohlc(df)
    n = len(C); atr = _atr(H, L, C)
    sma = pd.Series(C).rolling(sma_n, min_periods=5).mean().values
    don_hi = pd.Series(H).rolling(don_n, min_periods=5).max().shift(1).values
    don_lo = pd.Series(L).rolling(don_n, min_periods=5).min().shift(1).values

    day_R = np.zeros(n); day_min = np.zeros(n); traded = np.zeros(n, int)
    in_pos = 0; entry = 0.0; stop_pts = 0.0; dirn = 0
    for d in range(1, n):
        a = atr[d-1]
        if not (a == a) or a <= 0:
            continue
        # ---- manage an open position over today ----
        if in_pos:
            base = C[d-1]                       # day starts from prior close
            # intraday worst floating (from prior close), in R
            worst = (L[d]-base) if dirn > 0 else (base-H[d])
            day_min[d] = worst/stop_pts
            stop_px = entry - dirn*stop_pts
            hit = (L[d] <= stop_px) if dirn > 0 else (H[d] >= stop_px)
            # exit signal evaluated on prior close (no look-ahead)
            sig_exit = (C[d-1] < sma[d-1]) if dirn > 0 else (C[d-1] > sma[d-1])
            if hit:
                day_R[d] = (dirn*(stop_px-base))/stop_pts; traded[d]=1
                in_pos = 0
            elif sig_exit:
                day_R[d] = (dirn*(C[d]-base))/stop_pts; traded[d]=1   # exit at today close
                in_pos = 0
            else:
                day_R[d] = (dirn*(C[d]-base))/stop_pts; traded[d]=1   # mark-to-market
            continue
        # ---- flat: look for an entry (signal on prior close, fill at today open) ----
        want = 0
        if kind == "trend":
            if C[d-1] > sma[d-1]: want = 1
            elif (not long_only) and C[d-1] < sma[d-1]: want = -1
        elif kind == "breakout":
            if (don_hi[d-1] == don_hi[d-1]) and C[d-1] >= don_hi[d-1]: want = 1
            elif (not long_only) and (don_lo[d-1] == don_lo[d-1]) and C[d-1] <= don_lo[d-1]: want = -1
        if want != 0:
            in_pos = 1; dirn = want; entry = O[d]; stop_pts = atr_mult*a
            base = O[d]                          # entered at today's open
            worst = (L[d]-base) if dirn>0 else (base-H[d])
            day_min[d] = worst/stop_pts
            stop_px = entry - dirn*stop_pts
            if (L[d] <= stop_px) if dirn>0 else (H[d] >= stop_px):
                day_R[d] = (dirn*(stop_px-base))/stop_pts; in_pos = 0
            else:
                day_R[d] = (dirn*(C[d]-base))/stop_pts
            traded[d] = 1
    return day_R, day_min, traded

def to_days(day_R, day_min, traded):
    return np.rec.fromarrays([day_R, day_min, traded], names="day_R,day_min_R,n")

def main():
    df = pd.read_pickle if False else __import__("strategies").prep(data.load())
    dates, O,H,L,C = daily_ohlc(df)
    print(f"daily bars: {len(C)}  {pd.Timestamp(dates[0]).date()}..{pd.Timestamp(dates[-1]).date()}")
    print("SWING (block-bootstrap MC, cost ignored = optimistic for swing) — 4-week focus")
    for kind, p in [("trend long", dict(kind="trend", long_only=True)),
                     ("trend l/s", dict(kind="trend", long_only=False)),
                     ("breakout long", dict(kind="breakout", long_only=True))]:
        for am in [2.0, 3.0, 4.0]:
            dR, dm, tr = swing(df, atr_mult=am, **p)
            days = to_days(dR, dm, tr)
            row=[]
            for T in [15,20,40]:
                m=max([ftmo.run_mc(days, r, T, n_paths=20000, seed=5, block=10)
                       for r in [0.005,0.0075,0.01,0.0125,0.015]], key=lambda x:x["pass_rate"])
                row.append("%2.0f/%2.0f"%(m["pass_rate"]*100, m["blow_rate"]*100))
            exp = dR[tr>0].mean() if (tr>0).any() else 0
            print(f"  {kind:14s} atr{am}: days-in-mkt {100*(tr>0).mean():3.0f}%  expR/day {exp:+.3f} | "
                  f"3wk {row[0]} 4wk {row[1]} 8wk {row[2]}")

if __name__ == "__main__":
    main()
