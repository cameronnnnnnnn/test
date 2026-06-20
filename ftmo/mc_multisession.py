"""
NEW idea for the 1-MONTH goal: multi-session ORB (stack 14h/15h/16h US opens) to
raise frequency -> more shots to reach +10% inside 21 trading days. Day-based MC
allows multiple trades/day; each session fires independently with its own prob.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

DAYS,ctx=build_all(); NDAYS=len(DAYS)
def sess_pool(hr,stop=60):
    RR,MAE=orb_v4(DAYS,ctx,open_hr=hr,range_min=30,stop_pts=stop,be_at=1.0,trail_k=5.0,
                  cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True)
    return RR,MAE,len(RR)/NDAYS

print("Per-session edge (filters on, stop60):")
pools={}
for hr in (14,15,16):
    RR,MAE,p=sess_pool(hr); pools[hr]=(RR,MAE,p)
    print(f"  {hr}h: n={len(RR)} ({p*5:.1f}/wk) WR={(RR>0).mean()*100:4.1f}% "
          f"expR={RR.mean():+.3f} maxR={RR.max():.1f}")

START=15000.0;TARGET=1.10*START;TRAIL=0.10*START;CONS=0.50;MIN_TD=4;MONTH=21
def sim(sessions,r,rng,max_days=252):
    eq=START;peak=START;floor=START-TRAIL;dp=[];td=0
    for d in range(1,max_days+1):
        for (RR,MAE,p) in sessions:
            if rng.random()<p:
                i=rng.integers(len(RR));R=RR[i];mae=MAE[i];eb=eq
                if eb-r*mae*eb<=floor: return ("BLOW",d)
                eq=eb+r*R*eb;td+=1;dp.append(eq-eb)
                if eq<=floor: return ("BLOW",d)
                if eq>peak: peak=eq;floor=peak-TRAIL
                if eq>=TARGET and td>=MIN_TD:
                    w=[x for x in dp if x>0]
                    if w and max(w)<=CONS*sum(w): return ("PASS",d)
    return ("TO",max_days)

def report(name,sessions,r,N=12000,seed=7):
    rng=np.random.default_rng(seed)
    res=[sim(sessions,r,rng) for _ in range(N)]
    out=np.array([x[0] for x in res]); day=np.array([x[1] for x in res])
    P=out=="PASS";B=out=="BLOW"
    in1=(P&(day<=MONTH)).mean()*100; out1=(P&(day>MONTH)).mean()*100
    avg=day[P&(day>MONTH)].mean() if (P&(day>MONTH)).any() else np.nan
    tpw=sum(p for _,_,p in sessions)*5
    print(f"{name:22s} ({tpw:.1f}/wk) r={r*100:4.2f}% | pass<=1mo={in1:4.1f}%  "
          f"pass>1mo={out1:4.1f}% (avg{avg:4.0f}td) | blow={B.mean()*100:4.1f}%  to={(out=='TO').mean()*100:3.1f}%")

combos=[("US 16h only",[16]),("US 15h+16h",[15,16]),("US 14h+15h+16h",[14,15,16])]
print(f"\n1 month = {MONTH} trading days. Multi-session pass breakdown:\n")
for nm,hrs in combos:
    S=[pools[h] for h in hrs]
    for r in (0.01,0.015,0.02):
        report(nm,S,r)
    print()
