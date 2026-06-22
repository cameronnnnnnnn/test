"""
Focused: does a LONGER hard TP (4R/5R) with a TIGHT trail (1R/2R) from the extreme beat
the 2R-TP config? Idea: let winners aim higher but lock in pullbacks with a tight trail.
Reports WR + expR + consistency-rule pass/fail so it's directly comparable to mc_hardtp.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, tp_R, trail_k):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=trail_k,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,tp_R=tp_R)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm, df["R"].values

def coh(si,dm,rule,horizon):
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
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
    return "T",td

def metrics(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,True,MO) for si in st]; ev=[coh(si,dm,True,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    return p(ye,'P'), p(ev,'P'), p(ev,'F')

# (tp, trail): include the user's longer-TP+tight-trail ideas and the 2R baselines
COMBOS=[("2R + trail 5R*",2.0,5.0),("2R + trail 1R",2.0,1.0),
        ("3R + trail 1R",3.0,1.0),("3R + trail 2R",3.0,2.0),
        ("4R + trail 1R",4.0,1.0),("4R + trail 2R",4.0,2.0),
        ("5R + trail 1R",5.0,1.0),("5R + trail 2R",5.0,2.0),
        ("none(trail-only) 1R",None,1.0)]

for side,label in [("long","LONG-ONLY"),("both","BOTH-SIDES")]:
    print(f"\n{'='*78}\n  {label}  ($15k,+10%,10% trail,3% daily,r=1.25%,15h+16h,BE@1R,50% rule)\n{'='*78}")
    print(f"  {'config':<20}{'WR':>7}{'expR':>8}{'maxR':>7}   {'rule1mo':>8}{'rule4mo':>9}{'fail4mo':>9}")
    print("  "+"-"*68)
    for nm,tp,tr in COMBOS:
        dm,R=build(side,tp,tr)
        w=R[R>0]; wr=100*len(w)/len(R); expR=R.mean(); maxR=R.max()
        m=metrics(dm)
        star=" <- current EA" if nm.endswith("*") else ""
        print(f"  {nm:<20}{wr:>6.1f}%{expR:>+8.3f}{maxR:>+7.1f}   {m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%{star}")

print("\nVerdict line printed by eye: compare each longer-TP combo's rule1mo to the 2R rows.")
