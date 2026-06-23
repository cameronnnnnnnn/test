"""
FundedNext Bolt $50k vs Flex $50k. Bolt: +$3,000 target, $2,000 trailing EOD DD (locks at
start), $1,000 SOFT daily limit (hitting it pauses trading till next day, no breach), 40%
consistency, no min days. The soft daily limit is PROTECTIVE -- it caps a bad day so you
can't blow the $2,000 DD in one session -> should make higher sizing safer than Flex.

Sweeps risk (micros) for Bolt with the soft-limit circuit breaker, vs Flex (no daily limit),
to see if Bolt lets you size up profitably. 80pt stop, 1 MNQ = $160/R = 0.32% of $50k.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=50000.; LOCK=START; CONS=0.40; MO=21; HORIZON=252

def build(side, tp_R=3.0):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,tp_R=tp_R,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

def coh(si,dm,r,horizon,TGTP,ML,SOFT):
    TARGET=START+TGTP; eq=START; floor=START-ML; td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq
        for (R,MAE) in dm.get(day,[]):
            if SOFT is not None and (eq-ds)<=-SOFT: break   # soft daily limit -> paused for the day
            low=eq-r*MAE*eq
            if low<=floor: return "F",td+1                  # hard trailing-DD breach
            eq=eq+r*R*eq
            if eq<=floor: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        floor=max(floor, min(LOCK, eq-ML))                  # trailing EOD DD, locks at start
        if eq>=TARGET:
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
    return "T",td

def metrics(dm,r,TGTP,ML,SOFT):
    st=range(len(ALLDAYS)-MO); N=len(st)
    mo=[coh(si,dm,r,MO,TGTP,ML,SOFT) for si in st]; ev=[coh(si,dm,r,HORIZON,TGTP,ML,SOFT) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    pe=[d for x,d in ev if x=='P']
    return p(mo,'P'), p(ev,'P'), p(ev,'F'), (np.median(pe) if pe else float('nan'))

MICROS=[(1,0.0032),(2,0.0064),(3,0.0096),(4,0.0128),(5,0.0160),(6,0.0192)]
# (name, TGTP, ML, SOFT)
ACCTS=[("FLEX  (+2500 / 1500DD / no daily)",2500.,1500.,None),
       ("BOLT  (+3000 / 2000DD / 1000 soft)",3000.,2000.,1000.)]
for side in ("long","both"):
    dm=build(side)
    for nm,TGTP,ML,SOFT in ACCTS:
        print(f"\n{side.upper()} | {nm}")
        print(f"  {'risk':<14}{'pass1mo':>9}{'eventual':>10}{'blow':>8}{'med days':>10}")
        print("  "+"-"*50)
        for nc,r in MICROS:
            m=metrics(dm,r,TGTP,ML,SOFT)
            print(f"  {str(nc)+' MNQ '+format(r*100,'.2f')+'%':<14}{m[0]:>8.1f}%{m[1]:>9.1f}%{m[2]:>7.1f}%{m[3]:>9.0f}td")
print("\nBolt costs $99.99 vs Flex $79.99. Compare eventual-pass-per-dollar and 1mo pass.")
