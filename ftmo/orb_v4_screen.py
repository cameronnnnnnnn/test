"""Stage 1: stop-size sweep + each of the 10 new levers individually vs the
1.1%-raw baseline. Metric = pass% / blow% (trailing DD, +10%) and WR/expR."""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4, mc

DAYS,ctx=build_all()
print(f"NAS100: {len(DAYS)} days (~3y, all I have)\n")
BASE=dict(open_hr=16,range_min=30,be_at=1.0,trail_k=5.0,cost=2.0,eod_hr=23,
          rng_filter=True,vol_confirm=True)

def ev(name,**ex):
    cfg={**BASE,**ex}
    RR,MAE=orb_v4(DAYS,ctx,**cfg)
    if len(RR)<20: print(f"{name:26s} few trades ({len(RR)})"); return None
    p,b=mc(RR,MAE)
    print(f"{name:26s} n={len(RR):4d} WR={(RR>0).mean()*100:4.1f}% expR={RR.mean():+.3f} "
          f"maxR={RR.max():4.1f} | PASS={p*100:4.1f}% BLOW={b*100:4.1f}%")
    return (name,len(RR),(RR>0).mean(),RR.mean(),p,b)

print("=== STOP-SIZE SWEEP (base config, 1.1% raw) ===")
for sp in (40,50,60,70,80,100,120):
    ev(f"stop={sp}pt", stop_pts=sp)
ev("stop=ATR x0.5", atr_stop=0.5)
ev("stop=ATR x0.75", atr_stop=0.75)
ev("stop=ATR x1.0", atr_stop=1.0)

print("\n=== BASELINE + each NEW lever (stop=60) ===")
base=ev("0 baseline")
ev("1 vwap_filter", vwap_filter=True)
ev("2 close_confirm", close_confirm=True)
ev("3 overnight_conf", overnight_conf=True)
for dw,nm in [(0,"Mon"),(1,"Tue"),(2,"Wed"),(3,"Thu"),(4,"Fri")]:
    ev(f"4 skip {nm}", dow_skip={dw})
ev("5 atr_regime 0.3-1.0", atr_regime=(0.3,1.0))
ev("5 atr_regime 0.5-1.0", atr_regime=(0.5,1.0))
ev("6 mom_into=10", mom_into=10)
ev("6 mom_into=20", mom_into=20)
ev("7 long-only", side="long")
ev("7 short-only", side="short")
ev("8 pyramid@2R", pyramid=True)
ev("9 chandelier 3ATR", chandelier=3.0)
ev("9 chandelier 5ATR", chandelier=5.0)
ev("10 fail_rev", fail_rev=True)
