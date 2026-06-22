"""
DIAGNOSTIC: at the moment equity first hits +10%, how big was the best single day
relative to total profit? Answers "was the old trail-only setup really tripping the
50% consistency rule, or is the rule too lenient to matter?"

For each forward-calendar start day, walk real trading days until equity first crosses
+10% (no rule applied yet). Record at that instant:
  - best single-day $ profit, total $ profit, ratio, and the $750/5% picture
Then report the distribution + the % of would-be passes that VIOLATE best-day<=50%.
Compares trail-only vs the 2R hard TP.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,ctx=build_all()
ALLDAYS=[pd.Timestamp(d) for (d,*_) in DAYS]
START=15000.; TARGET=1.1*START; TR=.10; DD=.03; MIN=4; MO=21; r=.0125; CONS=0.50

def build(side, tp_R):
    dfs=[]
    for hr in (15,16):
        RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,
            be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,
            side=side,tp_R=tp_R)
        dfs.append(pd.DataFrame({"date":pd.to_datetime(DTS),"R":RR,"MAE":MAE}))
    df=pd.concat(dfs,ignore_index=True); dm={}
    for d,g in df.groupby(df["date"].dt.normalize()):
        dm[pd.Timestamp(d)]=list(zip(g["R"].values,g["MAE"].values))
    return dm

def first_cross(si,dm,horizon=MO):
    """walk until equity first >=TARGET (>=MIN days), no rule. Return (best_day$, total$)
    at that moment, or None if it blows/times out first."""
    eq=START; pk=START; fl=pk*(1-TR); td=0; daypnl=[]
    for j in range(si,min(si+horizon,len(ALLDAYS))):
        day=ALLDAYS[j]; ds=eq; dl=eq
        for (R,MAE) in dm.get(day,[]):
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=fl: return None
            eq=eq+r*R*eq
            if eq>pk: pk=eq; fl=pk*(1-TR)
            if eq<=fl: return None
        td+=1; daypnl.append(eq-ds)
        if (ds-dl)/ds>=DD: return None
        if eq>=TARGET and td>=MIN:
            return max(daypnl), eq-START
    return None

def report(nm, side, tp):
    dm=build(side,tp)
    rows=[first_cross(si,dm) for si in range(len(ALLDAYS)-MO)]
    rows=[x for x in rows if x is not None]
    if not rows:
        print(f"{nm}: no paths reached +10% in 1 month"); return
    best=np.array([x[0] for x in rows]); tot=np.array([x[1] for x in rows])
    ratio=best/tot
    viol=ratio>CONS
    print(f"{nm}   ({len(rows)} paths reached +10% within 1 month)")
    print(f"  best single day, as % of total profit:  median {np.median(ratio)*100:.0f}%   "
          f"p25 {np.percentile(ratio,25)*100:.0f}%   p75 {np.percentile(ratio,75)*100:.0f}%")
    print(f"  best single day, in $:                   median ${np.median(best):,.0f}   "
          f"max ${best.max():,.0f}   ($750 = the 5% line)")
    print(f"  VIOLATE best-day>50% (cannot bank +10% yet): {viol.mean()*100:.0f}% of would-be passes")
    print(f"  of those, days over $750:                {(best>750).mean()*100:.0f}% of paths\n")

print(f"$15k, +10% target=$1,500, r=1.25% (~$187/R at start). Consistency: best day<=50% of profit.\n")
print("=== TRAIL-ONLY (the OLD setup) ===")
report("long-only  trail-only", "long", None)
report("both-sides trail-only", "both", None)
print("=== 2R HARD TP (the new setup) ===")
report("long-only  TP 2R", "long", 2.0)
report("both-sides TP 2R", "both", 2.0)
print("takeaway: the rule looks lenient ($750/day) but this strategy's winning paths to")
print("+10% are built FROM a couple of big days, so a large share trip it. The 2R cap is")
print("what pulls the typical best-day back under the 50%/$750 line.")
