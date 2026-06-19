"""
Refine NAS100 ORB on the US cash session (15h/16h server). Test stop size,
range length, trailing (capture more tail), target caps. THEN the honesty tests:
  - long vs short separately (is it just bull beta?)
  - WALK-FORWARD: first 60% (in-sample) vs last 40% (out-of-sample 2024-25).
Save the best trade list for the FTMO Monte Carlo.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from nas_intraday import orb, m

def stats(df,name,split=None):
    if df is None or len(df)==0: print(f"{name:42s} no trades"); return None
    R=df["R"].values; win=(R>0).mean(); exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9); wk=len(R)/153.0
    L=df[df["dir"]>0]["R"]; S=df[df["dir"]<0]["R"]
    line=(f"{name:42s} n={len(R):4d}({wk:.1f}/wk) win={win*100:4.1f}% expR={exp:+.3f} "
          f"PF={pf:.2f} maxR={R.max():4.1f} | L:{L.mean():+.2f} S:{S.mean():+.2f}")
    print(line)
    return df

print("=== stop-size sweep (open=16h, US cash) — tighter stop = bigger R per move ===")
for sm,sp in [("range",0),("fixed",40),("fixed",50),("fixed",60),("fixed",80)]:
    nm=f"open16 stop={sm}{sp if sm=='fixed' else ''} EOD"
    stats(orb(open_hr=16,range_min=30,stop_mode=sm,stop_pts=sp,eod_hr=23),nm)

print("\n=== range length + trailing (capture more tail), open=16h fixed50 ===")
stats(orb(open_hr=16,range_min=15,stop_mode="fixed",stop_pts=50,eod_hr=23),"r15 fixed50 EOD")
stats(orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,eod_hr=23),"r30 fixed50 EOD")
stats(orb(open_hr=16,range_min=60,stop_mode="fixed",stop_pts=50,eod_hr=23),"r60 fixed50 EOD")
stats(orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,trail_R=2.0,eod_hr=23),"r30 fixed50 trail2R")
stats(orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,trail_R=3.0,eod_hr=23),"r30 fixed50 trail3R")
stats(orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,target_R=3.0,eod_hr=23),"r30 fixed50 cap3R")
stats(orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,target_R=5.0,eod_hr=23),"r30 fixed50 cap5R")

print("\n=== same on open=15h ===")
stats(orb(open_hr=15,range_min=30,stop_mode="fixed",stop_pts=50,eod_hr=23),"open15 r30 fixed50 EOD")
stats(orb(open_hr=15,range_min=30,stop_mode="fixed",stop_pts=50,trail_R=3.0,eod_hr=23),"open15 r30 fixed50 trail3R")

# ---------- choose a candidate, then HONESTY TESTS ----------
def candidate(side="both"):
    return orb(open_hr=16,range_min=30,stop_mode="fixed",stop_pts=50,
               trail_R=3.0,eod_hr=23,side=side)

print("\n=== HONESTY: long-only vs short-only (is edge just bull beta?) ===")
stats(candidate("long"),  "candidate LONG only")
stats(candidate("short"), "candidate SHORT only")

print("\n=== HONESTY: WALK-FORWARD (chronological split) ===")
cand=candidate("both").sort_values("date").reset_index(drop=True)
cut=int(len(cand)*0.60)
ins=cand.iloc[:cut]; oos=cand.iloc[cut:]
print(f"  in-sample  : {ins['date'].min()} .. {ins['date'].max()}")
print(f"  out-sample : {oos['date'].min()} .. {oos['date'].max()}")
stats(ins,"  IN-SAMPLE (first 60%)")
stats(oos,"  OUT-OF-SAMPLE (last 40%)")

cand.to_pickle("ftmo/m1_nas/nas_orb_trades.pkl")
print(f"\nsaved candidate trades: n={len(cand)}")
