"""
Stress the one promising XAUUSD hour (13h, both sides +) for robustness on a
6.8-month sample. If it is real it must: hold in BOTH walk-forward halves, keep
both sides positive, and survive cost stress + neighbouring-hour/param checks.
If it only lives in one half or one side, it is noise from a short, +40% sample.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from xau_intraday import orb, stats

print("=== robustness of XAUUSD open=13h ===\n")
print("cost stress (range stop, EOD):")
for cs in (0.4,0.8,1.5,3.0):
    stats(orb(open_hr=13,stop_pts=8,eod_hr=20,cost=cs),f"open13 stop$8 cost${cs}")

print("\nstop / management sweep (overfit check — should be stable if real):")
for sp in (5,8,12,16):
    stats(orb(open_hr=13,stop_pts=sp,eod_hr=20),f"open13 stop${sp} EOD")
for tr in (2.0,3.0):
    stats(orb(open_hr=13,stop_pts=8,trail_R=tr,eod_hr=20),f"open13 stop$8 trail{tr}R")

print("\nneighbouring hours (real edge shouldn't vanish 1h away):")
for oh in (11,12,13,14):
    stats(orb(open_hr=oh,stop_pts=8,eod_hr=20),f"open={oh}h stop$8")

print("\n=== WALK-FORWARD (the decider) ===")
cand=orb(open_hr=13,stop_pts=8,eod_hr=20).sort_values("date").reset_index(drop=True)
cut=len(cand)//2
h1=cand.iloc[:cut]; h2=cand.iloc[cut:]
print(f"  first half : {h1['date'].min()} .. {h1['date'].max()}")
print(f"  second half: {h2['date'].min()} .. {h2['date'].max()}")
stats(h1,"  FIRST HALF")
stats(h2,"  SECOND HALF")
cand.to_pickle("ftmo/m1_nas/xau_orb_trades.pkl")
