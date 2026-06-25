"""
v3/combine.py — TRUE multi-instrument FTMO test. Builds each instrument's per-minute
account-R curve from its trades, aligns NAS + Gold on a common minute grid, sums them,
then derives the correct per-day (day_R, day_min_R) of the COMBINED account (the joint
intraday low, not the conservative sum). Both strategies are EOD-flat so floating=0 at
each day end. Answers: does stacking two uncorrelated edges raise the 4-week pass?
"""
import numpy as np, pandas as pd, strategies as S, engine, ftmo, data, data_xau

def minute_equity(df, trades):
    """per-minute account-R series (realized + open-trade floating), EOD-flat."""
    idx = df.index; close = df["close"].values; n = len(df)
    floating = np.zeros(n); realized_step = np.zeros(n)
    ents = idx.searchsorted(trades["entry_dt"].values)
    exts = idx.searchsorted(trades["exit_dt"].values)
    for e, x, d, entry, stop, R in zip(ents, exts, trades["dir"].values,
                                       trades["entry"].values, trades["stop_pts"].values, trades["R"].values):
        x = min(x, n-1)
        if x > e:
            floating[e:x] += d*(close[e:x]-entry)/stop
        realized_step[x] += R
    acct = floating + np.cumsum(realized_step)
    return pd.Series(acct, index=idx)

def days_from_curve(acct):
    """correct day_R / day_min_R from a per-minute account-R curve (EOD-flat)."""
    by = acct.groupby(acct.index.normalize())
    rows = {}
    prev_end = 0.0
    for day, s in by:
        dmin = (s - prev_end).min()      # worst intraday vs day start (prev close)
        dend = s.iloc[-1]
        rows[day] = (dend - prev_end, min(dmin, 0.0))
        prev_end = dend
    dd = pd.DataFrame(rows, index=["day_R","day_min_R"]).T
    return dd

def to_rec(dd, all_dates):
    base = pd.DataFrame(index=pd.DatetimeIndex(all_dates))
    base["day_R"] = 0.0; base["day_min_R"] = 0.0; base["n"] = 0
    base.loc[dd.index, "day_R"] = dd["day_R"].values
    base.loc[dd.index, "day_min_R"] = dd["day_min_R"].values
    base.loc[dd.index, "n"] = 1
    return base.reset_index().to_records(index=False)

def best(days, T, risks=(0.006,0.0075,0.01,0.0125,0.015)):
    res=[(r,ftmo.run_mc(days,r,T,n_paths=30000,seed=5)) for r in risks]
    r,m=max(res,key=lambda x:x[1]["pass_rate"]); return m["pass_rate"],m["blow_rate"],r

def main():
    nas = S.prep(data.load()); ad = np.array(sorted(nas["date"].unique()))
    adset = set(pd.Timestamp(x) for x in ad)
    gold = S.prep(data_xau.load(since="2022-10-15"))

    nas_tr = engine.simulate(nas, S.orb(nas, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
                             tp_R=4.0, be_R=0.0, trail_R=0.0)
                             + S.vwap_pullback(nas, stop_pts=40, tp_R=4.0, trail_R=0.0), cost_pts=3.0)
    gold_tr = engine.simulate(gold, S.orb(gold, open_min=15*60+30, or_min=15, stop_pts=7.0, vol_filter=True,
                              tp_R=4.0, be_R=0.0, trail_R=0.0), cost_pts=0.3)
    gold_tr = gold_tr[gold_tr["day"].isin(adset)]

    nasE = minute_equity(nas, nas_tr)
    goldE = minute_equity(gold, gold_tr)
    # align on union minute grid, ffill running totals, restrict to NAS date span
    grid = nasE.index.union(goldE.index)
    nasA = nasE.reindex(grid).ffill().fillna(0.0)
    goldA = goldE.reindex(grid).ffill().fillna(0.0)
    goldA = goldA[(goldA.index >= nasE.index[0]) & (goldA.index <= nasE.index[-1])]
    nasA = nasA.reindex(goldA.index).ffill().fillna(0.0)
    combE = nasA + goldA

    dN = to_rec(days_from_curve(nasE), ad)
    dG = to_rec(days_from_curve(goldE).loc[lambda d: d.index.isin(pd.DatetimeIndex(ad))], ad)
    dC = to_rec(days_from_curve(combE), ad)

    print("TRUE minute-aligned combined account (joint intraday low). 4-week focus.")
    for name, days in [("NAS only", dN), ("GOLD only", dG), ("NAS+GOLD", dC)]:
        out=[]
        for T in [15,20,30,40]:
            p,b,r = best(days, T); out.append(f"{p*100:2.0f}/{b*100:2.0f}")
        print(f"  {name:10s} 3wk {out[0]}  4wk {out[1]}  6wk {out[2]}  8wk {out[3]}")
    # combined daily Sharpe @1%
    dr = np.asarray(dC["day_R"])*0.01
    print(f"  combined daily Sharpe @1% ~ {dr.mean()/dr.std():.3f}  (NAS-only was ~0.04)")

if __name__ == "__main__":
    main()
