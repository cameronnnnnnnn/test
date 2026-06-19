"""
Find the BEST honest config: sweep stop size (win-rate vs tail tradeoff) through
the single-session FTMO deadline MC. Higher win rate -> fewer 10%-drawdown blow-ups
-> higher pass ceiling. Report 3wk / 8wk / unlimited at each config's best safe risk.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from nas_intraday import orb

START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_PASS=0.50; MIN_DAYS=4

def run(RR,MAE,r,deadline,rng):
    eq=START; day_profits=[]; nd=0
    while nd<deadline:
        i=rng.integers(len(RR)); R=RR[i]; mae=MAE[i]; peak=eq
        if r*mae*eq/peak>=DAILY_BUF: pnl=-DAILY_BUF*peak
        else:
            pnl=r*R*eq
            if pnl<-DAILY_BUF*peak: pnl=-DAILY_BUF*peak
        eq+=pnl; nd+=1; day_profits.append(pnl)
        if eq<=GLOBAL: return "FAIL"
        if eq>=TARGET and nd>=MIN_DAYS:
            wins=[p for p in day_profits if p>0]
            if wins and max(wins)<=CONS_PASS*sum(wins): return "PASS"
    if eq>=TARGET and nd>=MIN_DAYS:
        wins=[p for p in day_profits if p>0]
        if wins and max(wins)<=CONS_PASS*sum(wins): return "PASS"
    return "TIMEOUT"

def mc(RR,MAE,r,dl,n=5000):
    rng=np.random.default_rng(3)
    res=pd.Series([run(RR,MAE,r,dl,rng) for _ in range(n)])
    return (res=="PASS").mean(),(res=="FAIL").mean()

configs=[("stop50 trail3",dict(stop_pts=50,trail_R=3.0)),
         ("stop60 trail3",dict(stop_pts=60,trail_R=3.0)),
         ("stop80 trail3",dict(stop_pts=80,trail_R=3.0)),
         ("stop80 trail2",dict(stop_pts=80,trail_R=2.0)),
         ("stop100 trail3",dict(stop_pts=100,trail_R=3.0))]

print("Config sweep through FTMO deadline MC (open=16h US, real M1):\n")
print(f"{'config':16s}{'expR':>7s}{'win%':>6s}{'maxR':>6s}  "
      f"{'3wk@r=1.5':>12s}{'8wk@r=1.0':>12s}{'unlim@r=1.0':>13s}")
for nm,cfg in configs:
    df=orb(open_hr=16,range_min=30,stop_mode="fixed",eod_hr=23,**cfg)
    RR=df["R"].values; MAE=df["MAE_R"].values
    p3,b3=mc(RR,MAE,0.015,15)
    p8,b8=mc(RR,MAE,0.010,40)
    pu,bu=mc(RR,MAE,0.010,250)
    print(f"{nm:16s}{RR.mean():+7.3f}{(RR>0).mean()*100:6.1f}{RR.max():6.1f}  "
          f"  P{p3*100:4.1f}/B{b3*100:4.1f} P{p8*100:4.1f}/B{b8*100:4.1f}  "
          f"P{pu*100:4.1f}/B{bu*100:4.1f}")
