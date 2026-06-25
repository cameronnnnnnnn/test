"""
Conditional Monte Carlo from the CURRENT live state (new $15k demo, night 1 done).
Start: balance $15,832.16, one completed green day of +$832.16 already on the books
(counts toward the 50% consistency rule), 1 of the 4 min trading days used.
Forward days sampled i.i.d. from the strategy's daily P&L distribution (both-sides,
3R TP per the v1.41 fix). r=1.25%/trade.

Pass  = balance reaches $16,500 (+10%) AND >=4 trading days AND best single day <= 50%
        of the sum of all positive days (the existing $832 day included).
Blow  = equity hits the max-drawdown floor, or a single day loses >=3%.
Reports, out of 10,000 runs: % pass and % blow within the NEXT MONTH (21 trading days)
and EVENTUALLY (up to 1 year). Floor shown both ways: FTMO's true STATIC $13,500, and
the stricter TRAILING peak-10% our sprint models used.
"""
import sys; sys.path.insert(0,'ftmo')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()

# daily P&L structure: both-sides, 3R TP (the fixed EA)
dfs=[]
for hr in (15,16):
    RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,be_at=1.0,
        trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side='both')
    dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
df=pd.concat(dfs,ignore_index=True)
DLIST=[list(zip(g['R'].values,g['MAE'].values)) for _,g in df.groupby(df['date'].dt.normalize())]
ND=len(DLIST)

BAL0=15832.16; INIT=15000.; TARGET=16500.; r=0.0125; DD=0.03; MIN=4; CONS=0.50
EXIST=832.16; TD0=1; STATIC=13500.; N=10000; MONTH=21; EVENT=252

def sim(floor_mode,horizon,rng):
    eq=BAL0; peak=BAL0
    floor=STATIC if floor_mode=='static' else peak*0.9
    daypnl=[EXIST]; td=TD0
    for _ in range(horizon):
        day=DLIST[rng.integers(ND)]; ds=eq; dl=eq; blown=False
        for (R,MAE) in day:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: return 'B'
            eq=eq+r*R*eq
            if floor_mode=='trail' and eq>peak: peak=eq; floor=peak*0.9
            if eq<=floor: return 'B'
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return 'B'
        if eq>=TARGET and td>=MIN:
            pos=[x for x in daypnl if x>0]
            if pos and max(pos)<=CONS*sum(pos): return 'P'
    return 'T'

print("10,000-run MC from current state: balance $15,832.16, +$832 day on the books,")
print("both-sides + 3R TP, r=1.25%. Pass=+10% & consistency-clear; Blow=hit max DD or 3% day.\n")
print(f"{'floor model':<26}{'window':<10}{'PASS':>8}{'BLOW':>8}{'still going':>13}")
print("-"*65)
for floor_mode,label in [('static','STATIC $13,500 (true FTMO)'),('trail','TRAILING peak-10% (strict)')]:
    for hz,wname in [(MONTH,'1 month'),(EVENT,'eventual')]:
        rng=np.random.default_rng(42)
        out=[sim(floor_mode,hz,rng) for _ in range(N)]
        p=100*out.count('P')/N; b=100*out.count('B')/N; t=100*out.count('T')/N
        print(f"{label:<26}{wname:<10}{p:>7.1f}%{b:>7.1f}%{t:>12.1f}%")
    print()
