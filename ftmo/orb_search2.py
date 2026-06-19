"""
Stage 2: combination search over the non-harmful levers, pick the best by
8-week pass (tie-break lower blow-up), then WALK-FORWARD validate the winner
and print its full deadline x risk table.
Levers searched: rng_filter, vol_confirm, early_break(60), anti_streak(MC).
(retest/atr_stop/range_stop/partial/reentry/gap_filter were harmful -> excluded.)
"""
import sys, os, itertools; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v3 import build_all, orb_v3, mc

DAYS,ctx=build_all()
BASE=dict(open_hr=16,range_min=30,stop_pts=60,be_at=1.0,trail_k=3.0,cost=2.0,eod_hr=23)

print("=== COMBINATION SEARCH ===")
levers=["rng_filter","vol_confirm","early_break","anti_streak"]
rows=[]
for combo in itertools.product([False,True],repeat=len(levers)):
    d=dict(zip(levers,combo))
    extra={}
    if d["rng_filter"]: extra["rng_filter"]=True
    if d["vol_confirm"]: extra["vol_confirm"]=True
    if d["early_break"]: extra["early_break"]=60
    anti=d["anti_streak"]
    RR,MAE=orb_v3(DAYS,ctx,**{**BASE,**extra})
    if len(RR)<20: continue
    p8,b8=mc(RR,MAE,0.010,40,anti_streak=anti)
    p3,b3=mc(RR,MAE,0.015,15,anti_streak=anti)
    rows.append({"combo":"+".join([k for k,v in d.items() if v]) or "baseline",
                 "n":len(RR),"expR":RR.mean(),"p3":p3,"b3":b3,"p8":p8,"b8":b8})
R=pd.DataFrame(rows).sort_values("p8",ascending=False)
for _,x in R.iterrows():
    print(f"  {x.combo:42s} n={x.n:4d} expR={x.expR:+.3f} | "
          f"3wk P{x.p3*100:4.1f}/B{x.b3*100:4.1f}  8wk P{x.p8*100:4.1f}/B{x.b8*100:4.1f}")

best=R.iloc[0]
print(f"\nWINNER: {best.combo}")

# ---- walk-forward validate the winning config ----
win_extra={}
if "rng_filter" in best.combo: win_extra["rng_filter"]=True
if "vol_confirm" in best.combo: win_extra["vol_confirm"]=True
if "early_break" in best.combo: win_extra["early_break"]=60
RR,MAE,DTS=orb_v3(DAYS,ctx,with_dates=True,**{**BASE,**win_extra})
order=np.argsort([pd.Timestamp(x) for x in DTS])
RR=RR[order]; MAE=MAE[order]; DTS=[DTS[i] for i in order]
cut=int(len(RR)*0.6)
print("\n=== WALK-FORWARD of winner ===")
print(f"  in-sample : {pd.Timestamp(DTS[0]).date()}..{pd.Timestamp(DTS[cut-1]).date()} "
      f"n={cut} expR={RR[:cut].mean():+.3f} win={(RR[:cut]>0).mean()*100:.1f}%")
print(f"  out-sample: {pd.Timestamp(DTS[cut]).date()}..{pd.Timestamp(DTS[-1]).date()} "
      f"n={len(RR)-cut} expR={RR[cut:].mean():+.3f} win={(RR[cut:]>0).mean()*100:.1f}%")

# ---- full deadline x risk table ----
anti = "anti_streak" in best.combo
print(f"\n=== WINNER full deadline x risk (anti_streak={anti}) ===")
print(f"{'deadline':11s} | " + " | ".join(f"r={r*100:.2f}%" for r in (0.01,0.0125,0.015,0.02)))
for dl,lab in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),(30,"6 weeks"),
               (40,"8 weeks"),(60,"12 weeks"),(120,"24 weeks")]:
    cells=[]
    for r in (0.01,0.0125,0.015,0.02):
        p,b=mc(RR,MAE,r,dl,n=8000,anti_streak=anti)
        cells.append(f"P{p*100:4.1f} B{b*100:4.1f}")
    print(f"{lab:11s} | " + " | ".join(cells))
pd.DataFrame({"R":RR,"MAE_R":MAE}).to_pickle("ftmo/m1_nas/nas_v3_best.pkl")
print(f"\nsaved winner -> nas_v3_best.pkl  (config: {best.combo})")
