"""
Which levers actually raise the 1-MONTH PASS rate (not just per-trade edge)?
Honest calendar test: start a fresh $15k challenge on EVERY trading day (overlapping
cohorts -> ~680 samples, smooth), classify PASS(+10%)/FAIL(-10% trail or -3% daily)/
TIMEOUT within 21 CALENDAR trading days. Higher PASS<=1mo is the sprint goal; FAIL is
the cost. Levers tested: +3rd session(14h), pyramid winners, fail_rev (2nd shot after a
stop), long-only, and a risk sweep.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]

def build_daymap(specs):
    dfs=[]
    for sp in specs:
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=sp["open_hr"],range_min=30,
                          stop_pts=sp.get("stop",80),be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,
                          rng_filter=True,vol_confirm=True,pyramid=sp.get("pyramid",False),
                          fail_rev=sp.get("fail_rev",False),side=sp.get("side","both"))
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True)
    dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm,len(df)

START=15000.0;TARGET=1.10*START;TRAILDD=0.10;DAILYDD=0.03;MINTD=4;MONTH=21
def cohort(si,dm,r):
    eq=START;peak=START;floor=peak*(1-TRAILDD);td=0
    for j in range(si,min(si+80,len(ALLDAYS))):
        day=ALLDAYS[j];ds=eq;dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq;dl=min(dl,low)
            if low<=floor: return "FAIL"
            eq=eq+r*R*eq
            if eq>peak:peak=eq;floor=peak*(1-TRAILDD)
            if eq<=floor: return "FAIL"
        td+=1
        if (ds-dl)/ds>=DAILYDD: return "FAIL"
        if eq>=TARGET and td>=MINTD: return "PASS"
        if td>=MONTH: return "TIMEOUT"
    return "TIMEOUT"

def evalcfg(name,specs,r):
    dm,nt=build_daymap(specs)
    starts=range(len(ALLDAYS)-MONTH)
    res=[cohort(si,dm,r) for si in starts];N=len(res)
    P=res.count("PASS");F=res.count("FAIL");T=res.count("TIMEOUT")
    tpd=nt/len({d for d in dm})
    print(f"{name:<26}{nt:>6}{tpd:>6.2f}{100*P/N:>9.1f}%{100*F/N:>9.1f}%{100*T/N:>9.1f}%")
    return P/N,F/N

S2=[{"open_hr":15},{"open_hr":16}]
S3=[{"open_hr":14},{"open_hr":15},{"open_hr":16}]
print(f"start-every-day cohorts, {len(ALLDAYS)} days, window={MONTH} calendar td, +10%/-10%/-3%\n")
print(f"{'config':<26}{'trades':>6}{'/day':>6}{'PASS<=1mo':>10}{'FAIL<=1mo':>9}{'TIMEOUT':>9}")
print("-"*76)
print("# frequency levers (more shots):")
evalcfg("15+16  r=1.25 (baseline)",S2,0.0125)
evalcfg("14+15+16  r=1.25",S3,0.0125)
evalcfg("14+15+16  r=1.0",S3,0.010)
print("# tail / extra-shot levers:")
evalcfg("15+16 +pyramid  r=1.25",[{"open_hr":15,"pyramid":True},{"open_hr":16,"pyramid":True}],0.0125)
evalcfg("15+16 +fail_rev r=1.25",[{"open_hr":15,"fail_rev":True},{"open_hr":16,"fail_rev":True}],0.0125)
evalcfg("15+16 long-only r=1.25",[{"open_hr":15,"side":"long"},{"open_hr":16,"side":"long"}],0.0125)
print("# risk sweep on the baseline (speed vs blow):")
for r in (0.010,0.015,0.0175,0.020,0.025):
    evalcfg(f"15+16  r={r*100:.2f}",S2,r)
print("\nread: PASS up is good ONLY if FAIL doesn't rise as much. frequency levers (more")
print("sessions/shots) lift PASS while holding or LOWERING blow; risk just trades them off.")
