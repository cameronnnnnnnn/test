"""
Does filtering the SPRINT to medium/high-volatility days actually help the FTMO odds?
atrpct is a TRAILING ATR percentile (causal, known before the open) -> legit to filter on.
Trade-off: higher expR per trade BUT fewer trades, and the sprint needs frequency.
Run the same FTMO day-bootstrap MC for several atrpct bands and compare.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()

def seq(band):
    def tr(hr):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
                          be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,
                          vol_confirm=True,atr_regime=band)
        return pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE})
    df=pd.concat([tr(15),tr(16)],ignore_index=True).sort_values("date").reset_index(drop=True)
    days=[list(zip(g["R"].values,g["MAE"].values)) for _,g in df.groupby(df["date"].dt.normalize())]
    return df,days

START=15000.0;TARGET=1.10*START;TRAILDD=0.10;DAILYDD=0.03;MINTD=4;MONTH=21;r=0.0125
def sim(days,rng,maxd=252):
    eq=START;peak=START;floor=START*(1-TRAILDD);td=0;N=len(days)
    while td<maxd:
        dt=days[rng.integers(N)];ds=eq;dl=eq
        for (R,MAE) in dt:
            low=eq-r*MAE*eq;dl=min(dl,low)
            if low<=floor: return "blow",td
            eq=eq+r*R*eq
            if eq>peak:peak=eq;floor=peak*(1-TRAILDD)
            if eq<=floor: return "blow",td
        td+=1
        if (ds-dl)/ds>=DAILYDD: return "blow",td
        if eq>=TARGET and td>=MINTD: return "pass",td
    return "timeout",td
def mc(days,N=20000,seed=7):
    rng=np.random.default_rng(seed);o=[sim(days,rng) for _ in range(N)]
    oc=np.array([x[0] for x in o]);dy=np.array([x[1] for x in o]);P=oc=="pass"
    return dict(p1=(P&(dy<=MONTH)).mean()*100,pl=(P&(dy>MONTH)).mean()*100,
                blow=(oc=="blow").mean()*100,to=(oc=="timeout").mean()*100,
                med=np.median(dy[P]) if P.any() else np.nan)

bands=[("all days (baseline)",None),("low vol  (0.0-0.5)",(0.0,0.5)),
       ("medium+  (0.33-1.0)",(0.33,1.0)),("high vol (0.5-1.0)",(0.5,1.0)),
       ("top-third(0.66-1.0)",(0.66,1.0))]
print(f"SPRINT 15h+16h, r={r*100:.2f}%, $15k, +10%/10% trail/3% daily, 1mo={MONTH}td (N=20000)\n")
hdr=f"{'filter':<22}{'trades':>7}{'/day':>6}{'expR':>7}{'pass<=1mo':>11}{'pass>1mo':>10}{'BLOW':>7}{'total':>7}{'medT':>7}"
print(hdr);print("-"*len(hdr))
for nm,b in bands:
    df,days=seq(b)
    if len(df)<30: print(f"{nm:<22} too few trades"); continue
    m=mc(days)
    print(f"{nm:<22}{len(df):>7}{len(df)/len(days):>6.2f}{df['R'].mean():>+7.3f}"
          f"{m['p1']:>10.1f}%{m['pl']:>9.1f}%{m['blow']:>6.1f}%{m['p1']+m['pl']:>6.1f}%{m['med']:>6.0f}td")
print("\nnote: 'pass<=1mo' is the sprint metric. fewer trades -> slower -> usually LOWER 1mo pass,")
print("even when expR/trade is higher. frequency tends to beat per-trade edge for a 21-day sprint.")
