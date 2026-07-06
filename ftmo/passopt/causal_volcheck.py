"""
LOOKAHEAD CHECK on the vol-regime filter. orb_v4's atr_regime uses ctx[day]['atrpct'],
whose daily ATR includes that day's own high/low/close -> not known at the ORB entry time.
Rebuild a CAUSAL ctx where each day's regime = the PRIOR trading day's atrpct, and compare:
  (a) no filter, (b) vol-regime with the original (lookahead) ctx, (c) vol-regime CAUSAL.
If (c) collapses vs (b), the result was lookahead-inflated and must be rejected.
Honest contiguous forward-calendar MC, 0.50% risk, static floor.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,CTX=build_all()

# build CAUSAL ctx: each trading day's atrpct := previous trading day's atrpct
order=[d[0] for d in DAYS]
CAUSAL={}
prev=np.nan
for day in order:
    cur=CTX.get(day,{}).get('atrpct',np.nan)
    cc=dict(CTX.get(day,{})); cc['atrpct']=prev
    CAUSAL[day]=cc; prev=cur

START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50

def trades(ctx, atr_regime):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,be_at=1.0,
            trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side='both',
            atr_regime=atr_regime)
        dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
    df=pd.concat(dfs,ignore_index=True).sort_values('date')
    return [(pd.Timestamp(d),list(zip(g['R'].values,g['MAE'].values))) for d,g in df.groupby(df['date'].dt.normalize())]

def walk(days,start,r,horizon=252):
    n=len(days); eq=START; floor=STATIC; dp=[]; td=0
    for s in range(horizon):
        _,day=days[(start+s)%n]; ds=eq; dl=eq
        for (R,MAE) in day:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: return 'B',td+1
            eq=eq+r*R*eq
            if eq<=floor: return 'B',td+1
        td+=1; dp.append(eq-ds)
        if (ds-dl)/ds>=DDAY: return 'B',td
        if eq>=TARGET and td>=MIN:
            pos=[x for x in dp if x>0]
            if pos and max(pos)<=CONS*sum(pos): return 'P',td
    return 'T',td

def evalcfg(days,r=0.005):
    res=[(days[i][0],*walk(days,i,r)) for i in range(len(days))]
    P=100*sum(1 for _,o,_ in res if o=='P')/len(res)
    B=100*sum(1 for _,o,_ in res if o=='B')/len(res)
    def hy(ts): return f"{ts.year}H{1 if ts.month<7 else 2}"
    byhy={}
    for d,o,_ in res: byhy.setdefault(hy(d),[]).append(o)
    worst=min(100*v.count('P')/len(v) for v in byhy.values())
    pdays=[t for _,o,t in res if o=='P']
    return P,B,worst,(np.median(pdays) if pdays else np.nan),sum(len(d) for _,d in days)

for name,ctx,reg in [('no filter',CTX,None),
                     ('vol 0.4-1.0 LOOKAHEAD',CTX,(0.4,1.0)),
                     ('vol 0.4-1.0 CAUSAL',CAUSAL,(0.4,1.0)),
                     ('vol 0.3-1.0 CAUSAL',CAUSAL,(0.3,1.0)),
                     ('vol 0.5-1.0 CAUSAL',CAUSAL,(0.5,1.0))]:
    d=trades(ctx,reg); P,B,worst,med,nt=evalcfg(d)
    print(f"{name:<24} PASS {P:5.1f}%  BLOW {B:4.1f}%  WORST-half {worst:5.1f}%  medPassDays {med:.0f}(trade-days)  trades {nt}")
print("\nCAUSAL must roughly match LOOKAHEAD to be valid. Median pass in TRADE-days; with the")
print("filter ~40% of calendar days are skipped, so calendar time ~= trade-days / 0.6.")
