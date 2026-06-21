"""
Per-month HISTORICAL cohort test of the final sprint product (15h+16h ORB, stop80,
BE@1R, trail5, filters, no overnight), r=1.25%. For each calendar month in the data,
start a fresh $15k challenge on day 1 and trade the REAL forward sequence.
Classify within 1 month (21 trading days): PASS(+10%) / FAIL(-10% EOD-trailing or
-3% daily) / TIMEOUT. Timeouts keep running -> record how long to eventually pass,
and their month-end / peak / lowest PnL during the month.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

DAYS,ctx=build_all()
def trades(hr):
    RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
                      be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True)
    return pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE})
df=pd.concat([trades(15),trades(16)],ignore_index=True).sort_values("date").reset_index(drop=True)
# group by trading date -> list of (R,MAE)
daymap={}
for d,g in df.groupby(df["date"].dt.normalize()):
    daymap[d]=list(zip(g["R"].values,g["MAE"].values))
dates=sorted(daymap.keys())
print(f"data: {dates[0].date()} .. {dates[-1].date()}  ({len(dates)} trading days, {len(df)} trades)")

START=15000.0; TARGET=1.10*START; TRAILDD=0.10; DAILYDD=0.03; MINTD=4; MONTH=21; r=0.0125

def run(si):
    eq=START; peak=START; floor=peak*(1-TRAILDD); td=0
    mpeak=START; mtrough=START; m_end=None
    outcome=None; oday=None; ftype=None
    for j in range(si,len(dates)):
        ds=eq; daylow=eq
        for (R,MAE) in daymap[dates[j]]:
            low=eq-r*MAE*eq; daylow=min(daylow,low)
            if low<=floor: outcome="FAIL"; ftype="trail"; eq=low; break
            eq=eq+r*R*eq
            if td<MONTH: mpeak=max(mpeak,eq); mtrough=min(mtrough,eq)
            if eq<=floor: outcome="FAIL"; ftype="trail"; break
            if eq>peak: peak=eq; floor=peak*(1-TRAILDD)
        td+=1
        if td<=MONTH: mpeak=max(mpeak,eq); mtrough=min(mtrough,eq)
        if td==MONTH: m_end=eq
        if outcome is None and (ds-daylow)/ds>=DAILYDD: outcome="FAIL"; ftype="daily"
        if outcome=="FAIL": oday=td; break
        if eq>=TARGET and td>=MINTD: outcome="PASS"; oday=td; break
    if m_end is None: m_end=eq
    return dict(outcome=outcome,oday=oday,ftype=ftype,td=td,
                m_end=m_end,mpeak=mpeak,mtrough=mtrough,resolved=outcome is not None)

# cohort start = first trading day of each calendar month
starts=[i for i in range(len(dates)) if i==0 or (dates[i].month!=dates[i-1].month)]
res=[run(si) for si in starts]
N=len(res)

# within-month classification
pin=[x for x in res if x["outcome"]=="PASS" and x["oday"]<=MONTH]
fin=[x for x in res if x["outcome"]=="FAIL" and x["oday"]<=MONTH]
tmo=[x for x in res if not (x["outcome"] and x["oday"]<=MONTH)]   # not resolved within month
pct=lambda k: 100*k/N
print(f"\n=== {N} monthly cohorts (start day-1 each month), r={r*100:.2f}% ===")
print(f"PASS within 1 month  : {len(pin):2d}/{N}  ({pct(len(pin)):4.1f}%)")
ftrail=len([x for x in fin if x['ftype']=='trail']); fdaily=len([x for x in fin if x['ftype']=='daily'])
print(f"FAIL within 1 month  : {len(fin):2d}/{N}  ({pct(len(fin)):4.1f}%)   [-10% trailing:{ftrail}  -3% daily:{fdaily}]")
print(f"TIMEOUT (ran over)   : {len(tmo):2d}/{N}  ({pct(len(tmo)):4.1f}%)")

# timeouts: keep running -> eventual pass time + their month stats
ev_pass=[x for x in tmo if x["outcome"]=="PASS"]
ev_fail=[x for x in tmo if x["outcome"]=="FAIL"]
ev_unre=[x for x in tmo if x["outcome"] is None]
pnl=lambda e:(e/START-1)*100
print(f"\n--- of the {len(tmo)} TIMEOUT cohorts (let them keep running) ---")
if ev_pass:
    od=np.array([x["oday"] for x in ev_pass])
    print(f"eventually PASS : {len(ev_pass)}  (avg {od.mean():.0f} trading-days total ~ {od.mean()/MONTH:.1f} months; "
          f"median {np.median(od):.0f}td)")
if ev_fail: print(f"eventually FAIL : {len(ev_fail)}  (avg day {np.mean([x['oday'] for x in ev_fail]):.0f}td)")
if ev_unre: print(f"still open at data end: {len(ev_unre)}")
if tmo:
    me=np.array([pnl(x["m_end"]) for x in tmo]); pk=np.array([pnl(x["mpeak"]) for x in tmo]); tr=np.array([pnl(x["mtrough"]) for x in tmo])
    print(f"\nTIMEOUT cohorts' PnL at the 1-month mark:")
    print(f"  avg final PnL (month end): {me.mean():+5.1f}%   (range {me.min():+.1f}%..{me.max():+.1f}%)")
    print(f"  avg PEAK PnL  in month   : {pk.mean():+5.1f}%")
    print(f"  avg LOWEST PnL in month  : {tr.mean():+5.1f}%")

# overall eventual pass rate (any time)
allpass=len([x for x in res if x["outcome"]=="PASS"])
print(f"\nOverall eventual PASS (any time): {allpass}/{N} ({pct(allpass):.1f}%)  "
      f"| total FAIL: {len([x for x in res if x['outcome']=='FAIL'])}/{N}")
