"""
Phase 2: (a) does GOLD have any positive ORB edge on the LAST 10 YEARS (2016-2026)
with the improved engine? (b) NAS100 + GOLD as a 2-instrument portfolio MC.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_lab import build_days, build_bias, orb_v2, mc
from orb_lab import START,TARGET,GLOBAL,DAILY_BUF,CONS_PASS,MIN_DAYS

# ---- GOLD last 10 years ----
gm=pd.read_pickle("ftmo/xau_full/xau20_m1.pkl")
gm=gm[gm["dt"]>="2016-01-01"].reset_index(drop=True)
gd=pd.read_pickle("ftmo/xau_full/xau20_daily.pkl")
gd=gd[gd["date"]>="2016-01-01"].reset_index(drop=True)
GD=build_days(gm); GB=build_bias(gd)
print(f"GOLD 10y: {len(GD)} days ({gm['dt'].min().date()}..{gm['dt'].max().date()})\n")

print("GOLD 10y ORB by hour (stop=$10, EOD, cost$0.4) — any positive?:")
best=None
for oh in range(8,21):
    RR,MAE=orb_v2(GD,GB,open_hr=oh,range_min=30,stop_pts=10.0,cost=0.40,
                  eod_hr=min(oh+7,23))
    if len(RR)<50: continue
    e=RR.mean()
    print(f"  open={oh:02d}h n={len(RR):4d} expR={e:+.3f} win={(RR>0).mean()*100:4.1f}% maxR={RR.max():4.1f}")
    if best is None or e>best[1]: best=(oh,e)
print(f"  best gold hour: {best[0]}h expR={best[1]:+.3f}")

print("\nGOLD 10y best-hour with improvements (be/trail/bias):")
oh=best[0]
for nm,cfg in [("plain",dict()),("be1",dict(be_at=1.0)),("trail3",dict(trail_k=3.0)),
               ("be1+trail3",dict(be_at=1.0,trail_k=3.0)),
               ("bias",dict(use_bias=True)),("be1+trail2+bias",dict(be_at=1.0,trail_k=2.0,use_bias=True))]:
    RR,MAE=orb_v2(GD,GB,open_hr=oh,stop_pts=10.0,cost=0.40,eod_hr=min(oh+7,23),**cfg)
    p8,b8=mc(RR,MAE,0.010,40)
    print(f"  {nm:18s} n={len(RR)} expR={RR.mean():+.3f} win={(RR>0).mean()*100:4.1f}% "
          f"8wk P{p8*100:4.1f}/B{b8*100:4.1f}")

# ---- NAS100 final config trades ----
nas=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl"); nd=pd.read_pickle("ftmo/m1_nas/nas_daily.pkl")
ND=build_days(nas); NB=build_bias(nd)
NR,NM=orb_v2(ND,NB,open_hr=16,stop_pts=60,be_at=1.0,trail_k=3.0,cost=2.0,eod_hr=23)
GR,GM2=orb_v2(GD,GB,open_hr=oh,stop_pts=10.0,be_at=1.0,trail_k=3.0,cost=0.40,eod_hr=min(oh+7,23))
print(f"\nNAS100 final: n={len(NR)} expR={NR.mean():+.3f}")
print(f"GOLD  final: n={len(GR)} expR={GR.mean():+.3f}")

# ---- PORTFOLIO MC: each day, trade BOTH (independent resample), risk split ----
def mc_combo(NR,NM,GR,GM2,r_each,deadline,n=5000,seed=9):
    rng=np.random.default_rng(seed); npass=nfail=0
    Ln=len(NR); Lg=len(GR)
    for _ in range(n):
        eq=START;dp=[];nd_=0;res="TIMEOUT"
        while nd_<deadline:
            i=rng.integers(Ln);j=rng.integers(Lg);peak=eq
            mae=r_each*NM[i]*eq + r_each*GM2[j]*eq   # combined floating loss
            if mae/peak>=DAILY_BUF: pnl=-DAILY_BUF*peak
            else:
                pnl=r_each*NR[i]*eq + r_each*GR[j]*eq
                if pnl<-DAILY_BUF*peak: pnl=-DAILY_BUF*peak
            eq+=pnl;nd_+=1;dp.append(pnl)
            if eq<=GLOBAL: res="FAIL";break
            if eq>=TARGET and nd_>=MIN_DAYS:
                w=[p for p in dp if p>0]
                if w and max(w)<=CONS_PASS*sum(w): res="PASS";break
        if res=="PASS": npass+=1
        elif res=="FAIL": nfail+=1
    return npass/n,nfail/n

print("\n=== NAS-only vs NAS+GOLD portfolio (each instr risked r_each; daily<=2.8%) ===")
print(f"{'deadline':10s} {'NAS r=1.5%':>16s} {'NAS+GOLD r=0.9% each':>24s}")
for dl,lab in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),(40,"8 weeks"),(80,"16 weeks")]:
    pn,bn=mc(NR,NM,0.015,dl,n=5000)
    pc,bc=mc_combo(NR,NM,GR,GM2,0.009,dl)
    print(f"{lab:10s}  P{pn*100:4.1f}/B{bn*100:4.1f}        P{pc*100:4.1f}/B{bc*100:4.1f}")
