"""
Test the user's STEPPED-LOCK exit vs the committed 3R config, under the FTMO 50% best-day
rule (best positive day <= 50% of positive-day sum, dilutable).

User's idea: hard TP 3R, BE@1R, and once price tags +2R lock the stop at +1R (discrete
step, not a continuous trail). Converts "ran to 2R then faded" trades from BE scratches
into +1R wins -> should lift WR and tighten the distribution, ideally without bleeding the
3R runners (the +1R stop only triggers on a full retrace to +1R).

Compares the exact spec plus a few neighbours.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, **kw):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side,**kw)
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

def edge(R):
    w=R[R>0]; l=R[R<=0]
    pf=(w.sum()/-l.sum()) if l.sum()<0 else float('inf')
    return 100*len(w)/len(R), R.mean(), pf, R.max()

# name -> kwargs for orb_v4
CONFIGS=[
 ("3R TP +BE1R (v1.40)",      dict(tp_R=3.0, be_at=1.0, trail_k=5.0)),
 ("3R +BE1R +lock1R@2R",      dict(tp_R=3.0, be_at=1.0, trail_k=None, lock_trig=2.0, lock_to=1.0)),  # user's exact spec
 ("3R +lock1R@2R (no BE)",    dict(tp_R=3.0, be_at=None, trail_k=None, lock_trig=2.0, lock_to=1.0)),
 ("3R +BE1R +lock1.5R@2R",    dict(tp_R=3.0, be_at=1.0, trail_k=None, lock_trig=2.0, lock_to=1.5)),
 ("3R +BE1R +lock1R@1.5R",    dict(tp_R=3.0, be_at=1.0, trail_k=None, lock_trig=1.5, lock_to=1.0)),
 ("3R +BE1R +lock2R@2.5R",    dict(tp_R=3.0, be_at=1.0, trail_k=None, lock_trig=2.5, lock_to=2.0)),
]

for side,label in [("long","LONG-ONLY"),("both","BOTH-SIDES")]:
    print(f"\n{'='*82}\n  {label}   (FTMO 50% best-day rule)\n{'='*82}")
    print(f"  {'config':<24}{'WR':>7}{'expR':>8}{'PF':>6}{'maxR':>6}   {'pass1mo':>8}{'pass4mo':>9}{'blow4mo':>9}")
    print("  "+"-"*70)
    base=None
    for nm,kw in CONFIGS:
        dm,R=build(side,**kw); wr,ex,pf,mx=edge(R); m=metrics(dm)
        if base is None: base=m[0]
        d=m[0]-base
        tag=" <- v1.40" if "v1.40" in nm else (f"  ({d:+.1f}pp)" if abs(d)>=0.1 else "  (=)")
        print(f"  {nm:<24}{wr:>6.1f}%{ex:>+8.3f}{pf:>6.2f}{mx:>+6.1f}   {m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>8.1f}%{tag}")

print("\nVerdict: does lock1R@2R beat plain 3R+BE on pass1mo? WR should rise; watch expR/pass1mo.")
