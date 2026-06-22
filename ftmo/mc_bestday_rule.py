"""
FTMO 1-Step '50% Best Day Rule' as actually written:
  best single POSITIVE day's profit <= 50% of the SUM of all positive days' profit.
  NOT a hard dollar cap, NOT a breach -- if your best day is too big you simply keep
  trading until the other green days grow the positive-sum enough to dilute it.

This differs from earlier models:
  - mc_consistency.py used denominator = NET profit (pos minus neg days) -> too harsh.
  - mc_consistency_strict.py used a hard $750 cap -> way too harsh.
Real denominator = sum of POSITIVE days only (larger) -> more lenient than both.

Re-sweeps the hard-TP lever under the correct rule to find the true optimum, for
long-only and both-sides. Metric: pass<=1mo, eventual<=4mo, blow-up<=4mo.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, tp_R):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,tp_R=tp_R)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm, df["R"].values

def coh(si,dm,horizon):
    """walk applying the REAL best-day rule (dilutable). P/F/T."""
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
            if pos and max(pos)<=CONS*sum(pos): return "P",td   # best day <= 50% of positive-day sum
            # else: keep trading to dilute (NOT a breach)
    return "T",td

def metrics(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,MO) for si in st]; ev=[coh(si,dm,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    pe=[d for x,d in ev if x=='P']
    return p(ye,'P'), p(ev,'P'), p(ev,'F'), (np.median(pe) if pe else float('nan'))

def edge(R):
    w=R[R>0]; return 100*len(w)/len(R), R.mean(), R.max()

CONFIGS=[("trail-only",None),("TP 4R",4.0),("TP 3R",3.0),("TP 2.5R",2.5),
         ("TP 2R",2.0),("TP 1.6R",1.6)]
for side,label in [("long","LONG-ONLY"),("both","BOTH-SIDES")]:
    print(f"\n{'='*74}\n  {label}   (50% BEST-DAY rule = best day <= 50% of positive-day sum)\n{'='*74}")
    print(f"  {'exit':<12}{'WR':>7}{'expR':>8}{'maxR':>7}   {'pass1mo':>8}{'pass4mo':>9}{'blow4mo':>9}{'medDays':>9}")
    print("  "+"-"*62)
    for nm,tp in CONFIGS:
        dm,R=build(side,tp); wr,ex,mx=edge(R); m=metrics(dm)
        print(f"  {nm:<12}{wr:>6.1f}%{ex:>+8.3f}{mx:>+7.1f}   {m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%{m[3]:>8.0f}td")

print("\nThis is the rule as FTMO states it. Compare to mc_hardtp.py (net-profit denom, harsher)")
print("and mc_consistency_strict.py ($750 hard cap, much harsher). Pick TP by pass1mo here.")
