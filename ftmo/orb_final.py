"""
Definitive comparison of the best NAS100 ORB configs (breakeven + trail tuning),
full FTMO deadline x risk Monte Carlo. Pick the winner, save its trades.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_lab import build_days, build_bias, orb_v2, mc

nas=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl"); nd=pd.read_pickle("ftmo/m1_nas/nas_daily.pkl")
ND=build_days(nas); NB=build_bias(nd)

configs={
 "A max-pass (trail3, no BE)":       dict(be_at=None,trail_k=3.0),
 "B balanced (BE@1R, trail3)":       dict(be_at=1.0, trail_k=3.0),
 "C early-BE (BE@0.5R, trail3)":     dict(be_at=0.5, trail_k=3.0),
 "D late-BE (BE@1.5R, trail3)":      dict(be_at=1.5, trail_k=3.0),
 "E safe (BE@1R, trail1.5)":         dict(be_at=1.0, trail_k=1.5),
}
trades={}
print("config edge stats (open=16h, stop=60, cost=2pt):")
for nm,cfg in configs.items():
    RR,MAE=orb_v2(ND,NB,open_hr=16,stop_pts=60,cost=2.0,eod_hr=23,**cfg)
    trades[nm]=(RR,MAE)
    print(f"  {nm:30s} n={len(RR)} expR={RR.mean():+.3f} win={(RR>0).mean()*100:4.1f}% "
          f"PF={RR[RR>0].sum()/-RR[RR<0].sum():.2f} maxR={RR.max():4.1f}")

print("\nFTMO pass% / blow% by deadline (best risk per goal):")
print(f"{'config':30s} | {'2wk r1.5':>11s} | {'3wk r1.5':>11s} | {'4wk r1.5':>11s} | "
      f"{'6wk r1.0':>11s} | {'8wk r1.0':>11s}")
for nm,(RR,MAE) in trades.items():
    cells=[]
    for r,dl in [(0.015,10),(0.015,15),(0.015,20),(0.010,30),(0.010,40)]:
        p,b=mc(RR,MAE,r,dl,n=8000)
        cells.append(f"P{p*100:4.1f}/B{b*100:4.1f}")
    print(f"{nm:30s} | " + " | ".join(cells))

# winner = B balanced; full risk sweep
print("\n=== WINNER 'B balanced (BE@1R, trail3)' — full deadline x risk ===")
RR,MAE=trades["B balanced (BE@1R, trail3)"]
print(f"{'deadline':11s} | " + " | ".join(f"r={r*100:.1f}%" for r in (0.01,0.0125,0.015,0.02)))
for dl,lab in [(10,"2 weeks"),(15,"3 weeks"),(20,"4 weeks"),(30,"6 weeks"),
               (40,"8 weeks"),(60,"12 weeks"),(120,"24 weeks")]:
    cells=[f"P{(p:=mc(RR,MAE,r,dl,n=8000))[0]*100:4.1f} B{p[1]*100:4.1f}"
           for r in (0.01,0.0125,0.015,0.02)]
    print(f"{lab:11s} | " + " | ".join(cells))

# save winner trades for the record
pd.DataFrame({"R":RR,"MAE_R":MAE}).to_pickle("ftmo/m1_nas/nas_best_trades.pkl")
print("\nsaved winner trades -> nas_best_trades.pkl")
