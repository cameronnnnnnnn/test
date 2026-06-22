"""
1-month pass rate for the CURRENT commit (v1.40: 3R TP, BE@1R, stop80, 15h+16h),
under the FTMO 50% best-day rule, across Friday-entry on/off x long-only/both-sides.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, skip_friday):
    dow=[4] if skip_friday else None   # pandas: Friday=4
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,dow_skip=dow)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm, df["R"].values

def coh(si,dm,horizon):
    eq=START; pk=START; fl=pk*(1-TR); td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq; dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=fl: return "F",td+1
            eq=eq+r*R*eq
            if eq>pk: pk=eq; fl=pk*(1-TR)
            if eq<=fl: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return "F",td
        if eq>=TARGET and td>=MIN:
            pos=[d for d in daypnl if d>0]
            if pos and max(pos)<=CONS*sum(pos): return "P",td
    return "T",td

def metrics(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,MO) for si in st]; ev=[coh(si,dm,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    return p(ye,'P'), p(ev,'P'), p(ev,'F')

print("Current commit v1.40 (3R TP, BE@1R, stop80, 15h+16h) | FTMO 50% best-day rule")
print(f"{'config':<34}{'WR':>7}{'#trades':>9}   {'pass1mo':>8}{'pass4mo':>9}{'blow4mo':>9}")
print("-"*78)
rows=[
 ("BOTH-SIDES, Friday OFF (DEFAULT)", "both", True),
 ("BOTH-SIDES, Friday ON",           "both", False),
 ("LONG-ONLY,  Friday OFF",          "long", True),
 ("LONG-ONLY,  Friday ON",           "long", False),
]
for nm,side,skipfri in rows:
    dm,R=build(side,skipfri); wr=100*(R>0).mean(); m=metrics(dm)
    star=" <- EA default" if "DEFAULT" in nm else ""
    print(f"{nm:<34}{wr:>6.1f}%{len(R):>9d}   {m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%{star}")
