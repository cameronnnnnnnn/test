"""Stage 3: optimise stop size WITH overnight_conf, confirm WF, then full
comprehensive MC (pass/blow/time-to-pass) at several risk levels on the winner."""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

DAYS,ctx=build_all()
BASE=dict(open_hr=16,range_min=30,be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,
          rng_filter=True,vol_confirm=True,overnight_conf=True)

START=15000.0; TARGET=1.10*START; TRAIL=0.10*START; MIN_DAYS=4; CONS=0.50
def simulate(RR,MAE,r,guard,max_steps,rng):
    eq=START;peak=START;floor=START-TRAIL;dp=[];n=0
    while n<max_steps:
        rr=r*0.5 if (guard and (eq-floor)/eq<0.05) else r
        if guard and (eq-floor)<=0.01*START: return("BLOW",n)
        i=rng.integers(len(RR));R=RR[i];mae=MAE[i];eb=eq
        if eb-rr*mae*eb<=floor: return("BLOW",n+1)
        eq=eb+rr*R*eb;n+=1;dp.append(eq-eb)
        if eq<=floor: return("BLOW",n)
        if eq>peak: peak=eq;floor=peak-TRAIL
        if eq>=TARGET and n>=MIN_DAYS:
            w=[p for p in dp if p>0]
            if w and max(w)<=CONS*sum(w): return("PASS",n)
    return("TO",n)
def full(RR,MAE,r,guard=False,N=15000,ms=300,seed=7):
    rng=np.random.default_rng(seed)
    res=[simulate(RR,MAE,r,guard,ms,rng) for _ in range(N)]
    o=np.array([x[0] for x in res]); s=np.array([x[1] for x in res])
    P=o=="PASS";B=o=="BLOW"
    return (P.mean()*100,B.mean()*100,(o=="TO").mean()*100,
            s[P].mean() if P.any() else np.nan, np.median(s[P]) if P.any() else np.nan)

# trades/week for time conversion
_,_,DTS=orb_v4(DAYS,ctx,with_dates=True,**BASE)
tpw=len(DTS)/((max(DTS)-min(DTS)).days/7)

print("=== stop-size sweep WITH overnight_conf (1.1% raw) ===")
for sp in (60,70,80,100):
    RR,MAE=orb_v4(DAYS,ctx,stop_pts=sp,**BASE)
    p,b,t,_,_=full(RR,MAE,0.011)
    print(f"  stop={sp:3d}pt  n={len(RR)}  WR={(RR>0).mean()*100:4.1f}%  expR={RR.mean():+.3f}  "
          f"PASS={p:4.1f}% BLOW={b:4.1f}%")
for a in (0.5,0.6):
    RR,MAE=orb_v4(DAYS,ctx,atr_stop=a,**BASE)
    p,b,t,_,_=full(RR,MAE,0.011)
    print(f"  stop=ATRx{a} n={len(RR)} WR={(RR>0).mean()*100:4.1f}% expR={RR.mean():+.3f} "
          f"PASS={p:4.1f}% BLOW={b:4.1f}%")

# WINNER: overnight + stop80
print("\n=== WINNER: overnight_conf + stop80 — comprehensive MC ===")
RR,MAE=orb_v4(DAYS,ctx,stop_pts=80,**BASE)
print(f"trades={len(RR)}  ~{tpw:.1f}/wk  WR={(RR>0).mean()*100:.1f}%  expR={RR.mean():+.3f}  "
      f"PF={RR[RR>0].sum()/-RR[RR<0].sum():.2f}  maxR={RR.max():.1f}")
print(f"\n{'risk':6s}{'guard':6s} | {'PASS':>6}{'BLOW':>6}{'TIME':>6} | {'avg wks→pass (med)':>20}")
for r in (0.0075,0.01,0.011,0.015):
    for g in (False,True):
        p,b,t,sm,md=full(RR,MAE,r,g)
        wk=f"{sm/tpw:4.1f} ({md/tpw:3.1f})" if not np.isnan(sm) else " - "
        print(f"{r*100:4.2f}% {'ON' if g else 'off':5s}| {p:5.1f}%{b:5.1f}%{t:5.1f}% | {wk:>20}")
    print()
