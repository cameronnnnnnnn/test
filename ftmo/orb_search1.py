"""
Stage 1: test each of the 10 improvements individually vs config-B baseline.
Keep the ones that improve 8-week pass or materially cut blow-up at equal pass.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v3 import build_all, orb_v3, mc

DAYS,ctx=build_all()
print(f"NAS100: {len(DAYS)} days\n")
BASE=dict(open_hr=16,range_min=30,stop_pts=60,be_at=1.0,trail_k=3.0,cost=2.0,eod_hr=23)

def evalcfg(name, anti=False, **extra):
    RR,MAE=orb_v3(DAYS,ctx,**{**BASE,**extra})
    if len(RR)<20:
        print(f"{name:24s} too few trades ({len(RR)})"); return None
    p3,b3=mc(RR,MAE,0.015,15,anti_streak=anti)
    p8,b8=mc(RR,MAE,0.010,40,anti_streak=anti)
    pu,bu=mc(RR,MAE,0.010,120,anti_streak=anti)
    print(f"{name:24s} n={len(RR):4d} expR={RR.mean():+.3f} win={(RR>0).mean()*100:4.1f}% "
          f"maxR={RR.max():4.1f} | 3wk P{p3*100:4.1f}/B{b3*100:4.1f} "
          f"8wk P{p8*100:4.1f}/B{b8*100:4.1f} 12wk P{pu*100:4.1f}/B{bu*100:4.1f}")
    return dict(name=name,n=len(RR),expR=RR.mean(),p8=p8,b8=b8,pu=pu,bu=bu)

print("BASELINE + each improvement alone (3wk@1.5%, 8wk@1.0%, 12wk@1.0%):\n")
res=[]
res.append(evalcfg("0 baseline (config B)"))
res.append(evalcfg("1 rng_filter", rng_filter=True))
res.append(evalcfg("2 early_break=30", early_break=30))
res.append(evalcfg("2 early_break=60", early_break=60))
res.append(evalcfg("3 retest", retest=True))
res.append(evalcfg("4 atr_stop=1.0", atr_stop=1.0))
res.append(evalcfg("4 atr_stop=0.5", atr_stop=0.5))
res.append(evalcfg("5 range_stop", range_stop=True))
res.append(evalcfg("6 partial@2R", partial=2.0))
res.append(evalcfg("7 reentry", reentry=True))
res.append(evalcfg("8 vol_confirm", vol_confirm=True))
res.append(evalcfg("9 gap_filter", gap_filter=True))
res.append(evalcfg("10 anti_streak (MC)", anti=True))

R=pd.DataFrame([r for r in res if r])
base=R.iloc[0]
print(f"\nDelta vs baseline (8-week pass and blow-up):")
for _,x in R.iterrows():
    print(f"  {x['name']:24s} dP8={ (x.p8-base.p8)*100:+5.1f}  dB8={ (x.b8-base.b8)*100:+5.1f}  "
          f"dP12={ (x.pu-base.pu)*100:+5.1f}")
