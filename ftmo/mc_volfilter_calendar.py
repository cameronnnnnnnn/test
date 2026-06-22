"""
HONEST calendar-time test of the volatility-day filter.
The day-bootstrap MC (mc_volfilter.py) counts '1 month = 21 TRADING days'. When you
filter out low-vol days, those still burn calendar time, so 21 trading days != 1 month.
Here we walk the REAL forward calendar (every market weekday; filtered-out days = no trade
but the clock still advances), start a fresh $15k challenge on day 1 of each month, and
classify PASS(+10%)/FAIL(-10% trail or -3% daily)/TIMEOUT within 21 CALENDAR trading days.
This is the apples-to-apples number for 'can I pass in one calendar month'.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]   # every market weekday, in order

def daymap_for(band):
    def tr(hr):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
                          be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,
                          vol_confirm=True,atr_regime=band)
        return pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE})
    df=pd.concat([tr(15),tr(16)],ignore_index=True)
    dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm,len(df)

START=15000.0;TARGET=1.10*START;TRAILDD=0.10;DAILYDD=0.03;MINTD=4;MONTH=21;r=0.0125
def run_cohort(si,dm):
    eq=START;peak=START;floor=peak*(1-TRAILDD);td=0
    for j in range(si,len(ALLDAYS)):
        day=ALLDAYS[j];ds=eq;dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq;dl=min(dl,low)
            if low<=floor: return ("FAIL",td+1)
            eq=eq+r*R*eq
            if eq>peak:peak=eq;floor=peak*(1-TRAILDD)
            if eq<=floor: return ("FAIL",td+1)
        td+=1
        if (ds-dl)/ds>=DAILYDD: return ("FAIL",td)
        if eq>=TARGET and td>=MINTD: return ("PASS",td)
        if td>=MONTH: return ("TIMEOUT",td)   # didn't resolve inside 1 calendar month
    return ("TIMEOUT",td)

starts=[i for i in range(len(ALLDAYS)) if i==0 or ALLDAYS[i].month!=ALLDAYS[i-1].month]
bands=[("all days (baseline)",None),("medium+  (0.33-1.0)",(0.33,1.0)),
       ("high vol (0.5-1.0)",(0.5,1.0)),("top-third(0.66-1.0)",(0.66,1.0))]
print(f"REAL forward calendar, {len(starts)} monthly cohorts, +10%/-10% trail/-3% daily, "
      f"r={r*100:.2f}%, pass window = {MONTH} CALENDAR trading days\n")
hdr=f"{'filter':<22}{'trades':>7}{'PASS<=1mo':>11}{'FAIL<=1mo':>11}{'TIMEOUT':>9}"
print(hdr);print("-"*len(hdr))
for nm,b in bands:
    dm,nt=daymap_for(b)
    res=[run_cohort(si,dm) for si in starts];N=len(res)
    P=sum(1 for o,_ in res if o=="PASS");F=sum(1 for o,_ in res if o=="FAIL")
    TO=sum(1 for o,_ in res if o=="TIMEOUT")
    print(f"{nm:<22}{nt:>7}{100*P/N:>10.1f}%{100*F/N:>10.1f}%{100*TO/N:>8.1f}%")
print("\n(TIMEOUT = survived the month without hitting +10% or blowing up; many of these")
print(" pass in month 2. The sprint metric is PASS<=1mo vs FAIL<=1mo.)")
