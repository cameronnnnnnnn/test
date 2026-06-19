"""
Equity curve for the FINAL strategy (NAS100 ORB + range filter + volume confirm).
Panel A: actual chronological backtest equity (real trade order, 2022-2025).
Panel B: Monte Carlo fan over 8 weeks vs FTMO +10% target / -10% limit.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from orb_v3 import build_all, orb_v3

DAYS,ctx=build_all()
BASE=dict(open_hr=16,range_min=30,stop_pts=60,be_at=1.0,trail_k=3.0,cost=2.0,eod_hr=23)
RR,MAE,DTS=orb_v3(DAYS,ctx,with_dates=True,rng_filter=True,vol_confirm=True,**BASE)
order=np.argsort([pd.Timestamp(x) for x in DTS])
RR=RR[order]; dates=[pd.Timestamp(DTS[i]) for i in order]
print(f"final strategy: {len(RR)} trades, expR={RR.mean():+.3f}, "
      f"win={(RR>0).mean()*100:.1f}%, total={RR.sum():.1f}R")

START=15000.0
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(15,6))

# ---- Panel A: actual chronological equity at a few risk levels ----
for r,col in [(0.005,"#888"),(0.01,"#1f77b4"),(0.0125,"#d62728")]:
    eq=START*np.cumprod(1+r*RR)
    ax1.plot(dates,eq,color=col,lw=1.4,label=f"r={r*100:.2f}% (×{eq[-1]/START:.1f})")
ax1.axhline(START,color="k",lw=0.8,ls=":")
ax1.set_title("A. Actual backtest equity — NAS100 ORB (final), 2022-2025\n"
              "real trade sequence, compounded",fontsize=11)
ax1.set_ylabel("Equity ($, start 15,000)"); ax1.legend(fontsize=9); ax1.grid(alpha=0.3)
ax1.tick_params(axis='x',rotation=30,labelsize=8)

# ---- Panel B: Monte Carlo fan over 8 weeks (40 trading days), r=1% ----
TARGET=1.10*START; LIMIT=0.90*START; DAILY=0.028; r=0.01
rng=np.random.default_rng(1); N=400; H=40
paths=np.zeros((N,H+1)); paths[:,0]=START
outcome=np.zeros(N)  # 1 pass, -1 blow, 0 timeout
for p in range(N):
    eq=START
    for d in range(H):
        R=RR[rng.integers(len(RR))]
        pnl=r*R*eq
        if pnl<-DAILY*eq: pnl=-DAILY*eq
        eq+=pnl; paths[p,d+1]=eq
        if eq<=0.905*START and outcome[p]==0: outcome[p]=-1
        if eq>=TARGET and outcome[p]==0: outcome[p]=1
    if outcome[p]==0: paths[p,:]=paths[p,:]  # keep
# color by outcome
for p in range(N):
    c = "#2ca02c" if outcome[p]==1 else ("#d62728" if outcome[p]==-1 else "#bbbbbb")
    a = 0.5 if outcome[p]!=0 else 0.15
    ax2.plot(range(H+1),paths[p],color=c,lw=0.6,alpha=a)
ax2.axhline(TARGET,color="#2ca02c",lw=1.5,ls="--",label="FTMO +10% target")
ax2.axhline(LIMIT,color="#d62728",lw=1.5,ls="--",label="FTMO -10% limit")
ax2.axhline(START,color="k",lw=0.8,ls=":")
pp=(outcome==1).mean()*100; bb=(outcome==-1).mean()*100
ax2.set_title(f"B. Monte Carlo — 400 runs, 8 weeks, r=1% (target+drawdown view)\n"
              f"reach target {pp:.0f}% (green) · blow {bb:.0f}% (red) "
              f"| full rules incl. consistency: ~49% pass (see playbook)",fontsize=10)
ax2.set_xlabel("trading days"); ax2.set_ylabel("Equity ($)")
ax2.legend(fontsize=9,loc="upper left"); ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("ftmo/equity_curve.png",dpi=110,bbox_inches="tight")
print("saved ftmo/equity_curve.png")
