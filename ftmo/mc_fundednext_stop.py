"""
FundedNext Flex $50k: stop-size is the key lever here, because the binding constraint is the
$1,500 trailing EOD drawdown. A TIGHTER stop = fewer $ per R = MORE R of drawdown room (and
more R-to-target). Sweeps stop size at 1 and 2 micros to find the survival sweet spot.
1 micro (MNQ) = $2/pt, so $risk/trade = 2*stop_pts*ncontracts; r = that / $50,000.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=50000.; TGTP=2500.; TARGET=START+TGTP; ML=1500.; LOCK=START; CONS=0.40; MO=21; HORIZON=252

def build(side, stop_pts, tp_R=3.0):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=stop_pts,
            be_at=1.0,trail_k=5.0,tp_R=tp_R,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side=side)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm, df["R"].values

def coh(si,dm,r,horizon):
    eq=START; floor=START-ML; td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq
            if low<=floor: return "F",td+1
            eq=eq+r*R*eq
            if eq<=floor: return "F",td+1
        td+=1; daypnl.append(eq-ds)
        floor=max(floor, min(LOCK, eq-ML))
        if eq>=TARGET:
            tot=eq-START
            if tot>0 and max(daypnl)<=CONS*tot: return "P",td
    return "T",td

def metrics(dm,r):
    st=range(len(ALLDAYS)-MO); N=len(st)
    mo=[coh(si,dm,r,MO) for si in st]; ev=[coh(si,dm,r,HORIZON) for si in st]
    p=lambda L,o:100*sum(1 for x,_ in L if x==o)/N
    pe=[d for x,d in ev if x=='P']
    return p(mo,'P'), p(ev,'P'), p(ev,'F'), (np.median(pe) if pe else float('nan'))

PTVAL=2.0  # $ per point per micro
for side in ("long","both"):
    print(f"\n{'='*78}\n  {side.upper()}  3R TP, 15h+16h | FundedNext Flex $50k (+$2,500 / $1,500 EOD trail)\n{'='*78}")
    print(f"  {'stop / size':<22}{'$risk/R':>8}{'R-room':>8}{'R-to-tgt':>9}   {'pass1mo':>8}{'eventual':>9}{'blow':>7}{'med':>6}")
    print("  "+"-"*70)
    for nc in (1,2):
        for stop in (40,50,60,80,100,120):
            dollar=PTVAL*stop*nc; r=dollar/START
            dm,_=build(side,stop)
            m=metrics(dm,r)
            rroom=ML/dollar; rtgt=TGTP/dollar
            print(f"  {str(stop)+'pt x'+str(nc)+'MNQ':<22}{'$'+format(dollar,'.0f'):>8}{rroom:>8.1f}{rtgt:>9.1f}   "
                  f"{m[0]:>7.1f}%{m[1]:>8.1f}%{m[2]:>6.1f}%{m[3]:>5.0f}")
        print()
print("R-room = drawdown room in R ($1500/$riskperR); R-to-tgt = R needed to hit +$2,500.")
print("Want: high eventual, low blow. Tighter stop buys R-room but needs more R to target.")
