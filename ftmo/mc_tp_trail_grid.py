"""
2D grid: hard TP (various R) x trailing stop (various R below extreme), under the
FTMO 50% consistency rule. Question: can a TP COMBINED with a tighter trail beat the
current best (TP 2R, trail 5R = trail effectively off)?

Logic of the interaction (orb_v4 exit order each bar): stop -> hard TP -> update extreme
-> BE@1R -> trail. So with e.g. TP 3R + trail 1R, a trade can exit three ways:
  - stop / BE (downside), - hard TP at 3R (capped upside),
  - trail 1R below the running extreme (locks in a pullback before TP is reached).
A tighter trail truncates give-back (raises WR, helps consistency) but exits runners
early (lowers expR). The grid finds the joint sweet spot.

Reports the consistency-rule forward-calendar MC (the realistic FTMO number) as matrices.
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
    df=pd.concat(dfs,ignore_index=True)
    dm={}
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
            if not rule: return "P",td
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
    return "T",td

def metrics(dm):
    st=range(len(ALLDAYS)-MO); N=len(st)
    ye=[coh(si,dm,True,MO) for si in st]
    ev=[coh(si,dm,True,84) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    return p(ye,'P'), p(ev,'P'), p(ev,'F')   # rule1mo, rule4mo, fail4mo

TPS   =[("none",None),("4R",4.0),("3R",3.0),("2.5R",2.5),("2R",2.0)]
TRAILS=[("1R",1.0),("1.5R",1.5),("2R",2.0),("3R",3.0),("5R",5.0)]

def matrix(side, which, title):
    print(f"\n{title}  [{which}]   rows=hard TP, cols=trail below extreme")
    hdr="TP\\trail"
    print(f"  {hdr:<9}"+"".join(f"{tn:>8}" for tn,_ in TRAILS))
    print("  "+"-"*(9+8*len(TRAILS)))
    best=(-1,None)
    for tpn,tp in TPS:
        cells=[]
        for trn,tr in TRAILS:
            dm,_=build(side,tp,tr)
            m=metrics(dm)
            val={"rule1mo":m[0],"rule4mo":m[1],"fail4mo":m[2]}[which]
            cells.append(val)
            if which!="fail4mo" and val>best[0]: best=(val,(tpn,trn))
        mark=lambda v: f"{v:>7.1f}%"
        print(f"  {tpn:<9}"+"".join(mark(c) for c in cells))
    if which!="fail4mo":
        print(f"  -> best {which}: {best[0]:.1f}%  at TP {best[1][0]} + trail {best[1][1]}")

for side,label in [("long","LONG-ONLY"),("both","BOTH-SIDES")]:
    print(f"\n{'='*70}\n  {label}   ($15k,+10%,10% trail,3% daily,r=1.25%,15h+16h,BE@1R,50% rule)\n{'='*70}")
    matrix(side,"rule1mo","PASS <=1 MONTH (with consistency rule)")
    matrix(side,"rule4mo","EVENTUAL PASS <=4mo (with consistency rule)")
    matrix(side,"fail4mo","BLOW-UP <=4mo (with consistency rule)")

print("\nBaseline to beat = current best: TP 2R, trail 5R (trail dominated).")
print("If a TP+tighter-trail cell beats it on rule1mo without raising fail4mo, that's the new config.")
