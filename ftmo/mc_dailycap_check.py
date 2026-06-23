"""
Does setting DailyProfitCap=$750 help or hurt under the REAL best-day rule?
Compares 3R TP with NO daily cap vs a $750 daily lock (stop new entries once day P&L>=750),
under the FTMO 50% best-day rule (best positive day <= 50% of positive-day sum, dilutable).
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

def coh(si,dm,horizon,daily_cap):
    eq=START; pk=START; fl=pk*(1-TR); td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq; dl=eq; dpl=0.0
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=fl: return "F",td+1
            if daily_cap is not None and dpl>=daily_cap: break  # DailyProfitCap: no more entries today
            g=r*R*eq; eq+=g; dpl+=g
            if eq>pk: pk=eq; fl=pk*(1-TR)
            if eq<=fl: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return "F",td
        if eq>=TARGET and td>=MIN:
            pos=[d for d in daypnl if d>0]
            if pos and max(pos)<=CONS*sum(pos): return "P",td
    return "T",td

def metrics(dm,cap):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,MO,cap) for si in st]; ev=[coh(si,dm,84,cap) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    return p(ye,'P'), p(ev,'P'), p(ev,'F')

print("3R TP under FTMO 50% best-day rule | DailyProfitCap off vs $750")
print(f"{'config':<34}{'pass1mo':>9}{'pass4mo':>9}{'blow4mo':>9}")
print("-"*61)
for side,label in [("long","long-only"),("both","both-sides")]:
    dm=build(side)
    for cap,cn in [(None,"DailyProfitCap OFF (0)"),(750.,"DailyProfitCap $750")]:
        m=metrics(dm,cap)
        print(f"{label+' / '+cn:<34}{m[0]:>8.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%")
    print()
