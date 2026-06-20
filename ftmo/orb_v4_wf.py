"""Stage 2: walk-forward the promising levers (overnight_conf, skip-Mon, wider stop,
mom_into). A real edge holds in BOTH chronological halves. Then combine survivors."""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4, mc

DAYS,ctx=build_all()
BASE=dict(open_hr=16,range_min=30,be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,
          rng_filter=True,vol_confirm=True)

def wf(name,**ex):
    RR,MAE,DTS=orb_v4(DAYS,ctx,with_dates=True,**{**BASE,**ex})
    if len(RR)<40: print(f"{name:24s} too few ({len(RR)})"); return
    o=np.argsort([pd.Timestamp(x) for x in DTS]); RR=RR[o]; MAE=MAE[o]
    cut=len(RR)//2; A,B=RR[:cut],RR[cut:]
    pf=lambda x: x[x>0].sum()/(-x[x<0].sum()+1e-9)
    p,b=mc(RR,MAE)
    flag="HOLDS" if (A.mean()>0.04 and B.mean()>0.04) else "FAILS WF"
    print(f"{name:24s} n={len(RR):4d} | 1st½ expR={A.mean():+.3f} PF={pf(A):.2f} | "
          f"2nd½ expR={B.mean():+.3f} PF={pf(B):.2f} | full PASS={p*100:4.1f}% [{flag}]")

print("WALK-FORWARD of promising levers (stop=60 unless noted):\n")
wf("baseline")
wf("overnight_conf", overnight_conf=True)
wf("skip Mon", dow_skip={0})
wf("skip Wed", dow_skip={2})
wf("mom_into=10", mom_into=10)
wf("stop80", stop_pts=80)
wf("ATRx0.5 stop", atr_stop=0.5)
print("\nWider-stop x overnight (do they stack and still hold?):")
wf("stop80 + overnight", stop_pts=80, overnight_conf=True)
wf("ATRx0.5 + overnight", atr_stop=0.5, overnight_conf=True)
wf("stop80 + mom_into10", stop_pts=80, mom_into=10)
