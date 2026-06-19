"""
Diversification test: trade TWO NAS100 sessions/day (London 07h + US 16h ORB).
More shots at the fat tail, equity smoothing -> can we lift the deadline pass rate
while keeping worst-case daily loss <= 2.8% (two positions sized at r each, but
capped so combined stop-out <= 2.8%)?
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from nas_intraday import orb

# two sessions; US (16h) is the strong one, London (07h) adds long-side shots
us = orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,trail_R=3.0,eod_hr=23)
ld = orb(open_hr=7, range_min=30,stop_mode="fixed",stop_pts=50,trail_R=3.0,eod_hr=14)
us["sess"]="US"; ld["sess"]="LD"
both=pd.concat([us,ld],ignore_index=True)
print("per-session edge:")
for nm,df in [("US 16h",us),("London 07h",ld),("combined",both)]:
    R=df["R"].values
    print(f"  {nm:11s} n={len(R):4d} expR={R.mean():+.3f} win={(R>0).mean()*100:4.1f}% "
          f"maxR={R.max():4.1f}")

# daily blocks: per date, list of (R, MAE_R)
blocks=[list(zip(g["R"].values,g["MAE_R"].values))
        for _,g in both.groupby("date",sort=True)]
print(f"\n{len(blocks)} trading days, avg {len(both)/len(blocks):.2f} trades/day")

START=15000.0; TARGET=1.10*START; GLOBAL=0.905*START
DAILY_BUF=0.028; CONS_PASS=0.50; MIN_DAYS=4

def run(r, deadline, rng, rcap=0.014):
    r=min(r,rcap)  # keep 2x positions under daily buffer
    eq=START; day_profits=[]; nd=0
    while nd<deadline:
        day=blocks[rng.integers(len(blocks))]
        peak=eq
        floatloss=sum(r*mae*eq for (_,mae) in day)
        if floatloss/peak>=DAILY_BUF:
            pnl=-DAILY_BUF*peak
        else:
            pnl=sum(r*R*eq for (R,_) in day)
            if pnl< -DAILY_BUF*peak: pnl=-DAILY_BUF*peak
        eq+=pnl; nd+=1; day_profits.append(pnl)
        if eq<=GLOBAL: return "FAIL"
        if eq>=TARGET and nd>=MIN_DAYS:
            wins=[p for p in day_profits if p>0]
            if wins and max(wins)<=CONS_PASS*sum(wins): return "PASS"
    if eq>=TARGET and nd>=MIN_DAYS:
        wins=[p for p in day_profits if p>0]
        if wins and max(wins)<=CONS_PASS*sum(wins): return "PASS"
    return "TIMEOUT"

def mc(r,deadline,n=6000):
    rng=np.random.default_rng(11)
    res=pd.Series([run(r,deadline,rng) for _ in range(n)])
    return (res=="PASS").mean(),(res=="FAIL").mean(),(res=="TIMEOUT").mean()

print("\nTWO-SESSION deadline pass rate (worst-case daily loss kept <=2.8%):")
print(f"{'deadline':12s}", *[f"r={r*100:.2f}%        " for r in (0.007,0.01,0.012,0.014)])
for dl,label in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),
                 (40,"8 weeks"),(80,"16 weeks"),(250,"unlimited")]:
    row=f"{label:12s}"
    for r in (0.007,0.01,0.012,0.014):
        p,f,to=mc(r,dl)
        row+=f" P={p*100:4.1f} B={f*100:4.1f}  "
    print(row)
print("\n(P = pass %, B = blow-up %)")
