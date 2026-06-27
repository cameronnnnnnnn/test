"""
v3/gold_sig.py — gold-specific intraday strategies (different from the US-open ORB),
scanned for DURABILITY over 22 years (positive across 3-year blocks = real edge).
EOD-flat (no overnight) so the 3% daily cap stays intraday. Server time (EET).
"""
import numpy as np, pandas as pd
from strategies import _day_groups, ExitSpec, SESS_END

def _arr(df):
    return (df["open"].values, df["high"].values, df["low"].values,
            df["close"].values, df["tickvol"].values.astype(float), df["tod"].values)

# A) ASIAN-RANGE breakout: range over [r0,r1] server, break after b_after, EOD-flat
def asian_breakout(df, r0=1*60, r1=9*60, b_after=10*60, stop_pts=7.0, mode="cont",
                   entry_by=20*60, spec=None):
    o,h,l,c,v,tod = _arr(df); spec = spec or ExitSpec(tp_R=4.0); orders=[]
    for day, gi in _day_groups(df).items():
        t = tod[gi]; rm = (t>=r0)&(t<r1)
        if rm.sum() < 60: continue
        rh = h[gi[rm]].max(); rl = l[gi[rm]].min()
        post = gi[(t>=b_after)&(t<=SESS_END)]
        if len(post) < 10: continue
        eod = post[-1]
        for b in post[:-1]:
            if tod[b] > entry_by: break
            up = h[b] >= rh; dn = l[b] <= rl
            if up or dn:
                d = (1 if up else -1)
                if mode=="fade": d = -d
                orders.append(dict(entry_bar=b, dir=d, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="asia")); break
    return orders

# B) TREND CONTINUATION: daily SMA trend filter + intraday breakout in that direction
def trend_cont(df, sma_n=20, open_min=15*60+30, or_min=30, stop_pts=7.0,
               counter=False, spec=None):
    o,h,l,c,v,tod = _arr(df); spec = spec or ExitSpec(tp_R=4.0)
    g = list(_day_groups(df).items())
    dclose = {day: c[gi[-1]] for day, gi in g}
    days = [d for d,_ in g]
    cl = pd.Series([dclose[d] for d in days])
    sma = cl.rolling(sma_n, min_periods=5).mean().shift(1).values
    pclose = cl.shift(1).values
    orders=[]; or_end = open_min + or_min
    for k in range(len(g)):
        if not (sma[k]==sma[k]): continue
        up = pclose[k] > sma[k]                  # prior close above SMA -> uptrend
        day, gi = g[k]; t = tod[gi]; om=(t>=open_min)&(t<or_end)
        if om.sum() < 10: continue
        rh = h[gi[om]].max(); rl = l[gi[om]].min()
        post = gi[(t>=or_end)&(t<=SESS_END)]
        if len(post) < 5: continue
        eod = post[-1]
        want = 1 if up else -1
        if counter: want = -want
        for b in post[:-1]:
            if want>0 and h[b] >= rh:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="tc")); break
            if want<0 and l[b] <= rl:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="tc")); break
    return orders
