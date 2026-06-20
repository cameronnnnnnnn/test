"""
1-MONTH Monte Carlo. Calendar-day based (each sim day a trade happens with the
config's real probability), so '1 month' = 21 trading days exactly and trade
frequency is modelled correctly. Rules: 60/80pt stop=1R, EOD trailing 10% DD,
consistency, min 4 trade-days, target +10%.
Reports per config/risk:  pass<=1mo | pass>1mo (+avg trading-days) | blow | timeout.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

DAYS,ctx=build_all(); NDAYS=len(DAYS)   # weekday trading days available
BASE=dict(open_hr=16,range_min=30,be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,
          rng_filter=True,vol_confirm=True)

def pool(**ex):
    RR,MAE=orb_v4(DAYS,ctx,**{**BASE,**ex})
    return RR,MAE,len(RR)/NDAYS      # p = prob a trade happens on a trading day

START=15000.0;TARGET=1.10*START;TRAIL=0.10*START;CONS=0.50;MIN_TD=4;MONTH=21
def sim(RR,MAE,p,r,rng,guard,max_days=252):
    eq=START;peak=START;floor=START-TRAIL;dp=[];td=0
    for d in range(1,max_days+1):
        if rng.random()<p:                       # a trade happens today
            rr=r*0.5 if (guard and (eq-floor)/eq<0.05) else r
            if guard and (eq-floor)<=0.01*START:
                return ("BLOW",d)
            i=rng.integers(len(RR));R=RR[i];mae=MAE[i];eb=eq
            if eb-rr*mae*eb<=floor: return ("BLOW",d)
            eq=eb+rr*R*eb;td+=1;dp.append(eq-eb)
            if eq<=floor: return ("BLOW",d)
            if eq>peak: peak=eq;floor=peak-TRAIL
            if eq>=TARGET and td>=MIN_TD:
                w=[x for x in dp if x>0]
                if w and max(w)<=CONS*sum(w): return ("PASS",d)
    return ("TO",max_days)

def report(name,RR,MAE,p,r,guard=False,N=12000,seed=7):
    rng=np.random.default_rng(seed)
    res=[sim(RR,MAE,p,r,rng,guard) for _ in range(N)]
    out=np.array([x[0] for x in res]); day=np.array([x[1] for x in res])
    P=out=="PASS";B=out=="BLOW"
    in1=(P&(day<=MONTH)).mean()*100
    out1=(P&(day>MONTH)).mean()*100
    avg_out=day[P&(day>MONTH)].mean() if (P&(day>MONTH)).any() else np.nan
    wr=(RR>0).mean()*100
    print(f"{name:30s} r={r*100:4.2f}% | WR={wr:4.1f}% | pass<=1mo={in1:4.1f}%  "
          f"pass>1mo={out1:4.1f}% (avg {avg_out:4.0f}td) | blow={B.mean()*100:4.1f}%  "
          f"timeout={(out=='TO').mean()*100:4.1f}%")

print(f"1 month = {MONTH} trading days. Data: {NDAYS} trading days.\n")
configs=[
 ("FREQUENT stop60", dict(stop_pts=60)),
 ("FREQUENT stop80 (hi WR)", dict(stop_pts=80)),
 ("FREQUENT stop40 (fat tail)", dict(stop_pts=40)),
 ("FREQUENT ATRx0.5 (hi WR)", dict(atr_stop=0.5)),
 ("OVERNIGHT stop80 (slow)", dict(stop_pts=80, overnight_conf=True)),
]
for nm,ex in configs:
    RR,MAE,p=pool(**ex)
    print(f"--- {nm}: {len(RR)} trades, {p*5:.1f}/wk, maxR={RR.max():.1f} ---")
    for r in (0.01,0.015,0.02,0.025):
        report(nm,RR,MAE,p,r)
    print()
