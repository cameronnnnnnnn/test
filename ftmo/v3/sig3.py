"""
v3/sig3.py — NEW intraday NAS100 signal families (distinct from v2's ORB family).
All emit engine orders; entry_bar=b fills at O[b+1] (no look-ahead). Server time.
"""
import numpy as np, pandas as pd
from strategies import _day_groups, ExitSpec, daily_atr, SESS_END

CASH = 16*60 + 30   # NYSE cash open in server time (EET/EEST)

def _arrs(df):
    return (df["open"].values, df["high"].values, df["low"].values,
            df["close"].values, df["tickvol"].values.astype(float), df["tod"].values)

# 1) GAP: today's cash open vs prior session close -> continuation or fade
def gap(df, gap_min=20, stop_pts=50, mode="cont", open_min=CASH, spec=None):
    o,h,l,c,v,tod = _arrs(df); spec = spec or ExitSpec(tp_R=4.0)
    g = list(_day_groups(df).items()); orders=[]
    for k in range(1, len(g)):
        day, gi = g[k]; pgi = g[k-1][1]
        psess = pgi[tod[pgi] <= SESS_END]
        if len(psess)==0: continue
        prev_close = c[psess[-1]]
        sess = gi[(tod[gi] >= open_min) & (tod[gi] <= SESS_END)]
        if len(sess) < 10: continue
        gp = o[sess[0]] - prev_close
        if abs(gp) < gap_min: continue
        d = (1 if gp>0 else -1)
        if mode=="fade": d = -d
        orders.append(dict(entry_bar=sess[0], dir=d, stop_pts=stop_pts, spec=spec,
                           eod_bar=sess[-1], day=day, tag="gap"))
    return orders

# 2) VOLATILITY EXPANSION: price moves k*ATR from the session open -> momentum
def vol_expand(df, k=0.5, stop_pts=50, atrn=14, open_min=CASH, entry_by=21*60, spec=None):
    o,h,l,c,v,tod = _arrs(df); spec = spec or ExitSpec(tp_R=4.0)
    atr = daily_atr(df, atrn); orders=[]
    for day, gi in _day_groups(df).items():
        sess = gi[(tod[gi] >= open_min) & (tod[gi] <= SESS_END)]
        if len(sess) < 30: continue
        a = atr.get(day, np.nan)
        if not (a==a) or a<=0: continue
        op = o[sess[0]]; thr = k*a; eod = sess[-1]
        for b in sess[1:-1]:
            if tod[b] > entry_by: break
            if h[b] >= op + thr:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="volx")); break
            if l[b] <= op - thr:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="volx")); break
    return orders

# 3) POWER HOUR: at decide time, ride the day's move so far into the close
def power_hour(df, decide=21*60, thr_pts=40, stop_pts=50, open_min=CASH, spec=None):
    o,h,l,c,v,tod = _arrs(df); spec = spec or ExitSpec(tp_R=4.0)
    orders=[]
    for day, gi in _day_groups(df).items():
        sess = gi[(tod[gi] >= open_min) & (tod[gi] <= SESS_END)]
        dec  = gi[(tod[gi] >= decide) & (tod[gi] <= SESS_END)]
        if len(sess) < 60 or len(dec) < 5: continue
        move = c[dec[0]] - o[sess[0]]
        if abs(move) < thr_pts: continue
        d = 1 if move>0 else -1
        orders.append(dict(entry_bar=dec[0], dir=d, stop_pts=stop_pts, spec=spec,
                           eod_bar=sess[-1], day=day, tag="power"))
    return orders

# 4) NARROW-RANGE breakout: small opening range (vs ATR) -> expansion breakout
def nr_break(df, or_min=30, max_ratio=0.25, stop_pts=50, open_min=CASH,
             entry_by=21*60, atrn=14, spec=None):
    o,h,l,c,v,tod = _arrs(df); spec = spec or ExitSpec(tp_R=4.0)
    atr = daily_atr(df, atrn); orders=[]
    or_end = open_min + or_min
    for day, gi in _day_groups(df).items():
        t = tod[gi]; om = (t>=open_min)&(t<or_end)
        if om.sum() < 5: continue
        rh = h[gi[om]].max(); rl = l[gi[om]].min(); a = atr.get(day, np.nan)
        if not (a==a) or a<=0: continue
        if (rh-rl) > max_ratio*a: continue          # only NARROW openings
        post = gi[(t>=or_end)&(t<=SESS_END)]
        if len(post) < 5: continue
        eod = post[-1]
        for b in post[:-1]:
            if tod[b] > entry_by: break
            if h[b] >= rh:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="nr")); break
            if l[b] <= rl:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="nr")); break
    return orders

REG = {"gap": gap, "vol_expand": vol_expand, "power_hour": power_hour, "nr_break": nr_break}
