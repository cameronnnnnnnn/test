"""
Efficient 22-year XAUUSD ORB engine. Pre-group M1 by day once, then scan fast.
Same validated breakout logic as NAS100. Gold cost in $ (stressed).
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

_m=pd.read_pickle("ftmo/xau_full/xau20_m1.pkl")
_m["date"]=_m["dt"].dt.normalize()
_m["minute"]=_m["dt"].dt.hour*60+_m["dt"].dt.minute
_m["dow"]=_m["dt"].dt.dayofweek
# pre-build per-day arrays (skip weekends)
DAYS=[]
for day,g in _m.groupby("date"):
    if g["dow"].iloc[0]>=5: continue
    DAYS.append((day,g["minute"].values,g["open"].values,g["high"].values,
                 g["low"].values,g["close"].values))
print(f"[xau20] {len(DAYS)} trading days pre-built", flush=True)
NWK=len(DAYS)/5

def orb(open_hr,range_min=30,stop_mode="fixed",stop_pts=8.0,target_R=None,
        trail_R=None,eod_hr=None,cost=0.40,side="both"):
    if eod_hr is None: eod_hr=min(open_hr+7,23)
    o0=open_hr*60; o1=open_hr*60+range_min; e1=eod_hr*60
    rows=[]
    for day,mn,O,H,L,C in DAYS:
        om=(mn>=o0)&(mn<o1)
        if om.sum()<range_min*0.5: continue
        rhi=H[om].max(); rlo=L[om].min(); rng=rhi-rlo
        if rng<=0: continue
        sm=(mn>=o1)&(mn<e1)
        if sm.sum()<10: continue
        sH=H[sm];sL=L[sm];sC=C[sm];sO=O[sm]
        pos=0;entry=0.0;stop_px=0.0;risk=0.0;ext=0.0;exitR=None;mae=0.0
        for i in range(len(sH)):
            if pos==0:
                if side in("both","long") and sH[i]>=rhi and sO[i]<rhi+rng:
                    pos=1;entry=max(rhi,sO[i]);risk=rng if stop_mode=="range" else stop_pts
                    stop_px=entry-risk;ext=entry
                elif side in("both","short") and sL[i]<=rlo:
                    pos=-1;entry=min(rlo,sO[i]);risk=rng if stop_mode=="range" else stop_pts
                    stop_px=entry+risk;ext=entry
                if pos!=0 and risk<=0: pos=0
                continue
            adv=(entry-sL[i]) if pos>0 else (sH[i]-entry);mae=max(mae,adv)
            if(pos>0 and sL[i]<=stop_px)or(pos<0 and sH[i]>=stop_px):
                exitR=(pos*(stop_px-entry)-cost)/risk;break
            ext=max(ext,sH[i]) if pos>0 else min(ext,sL[i])
            curR=(pos*(sC[i]-entry))/risk
            if target_R is not None and curR>=target_R:
                exitR=(pos*(sC[i]-entry)-cost)/risk;break
            if trail_R is not None:
                ts=ext-pos*trail_R*risk
                stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
        if pos!=0 and exitR is None: exitR=(pos*(sC[-1]-entry)-cost)/risk
        if pos!=0: rows.append((day,exitR,max(mae,0)/risk,pos))
    return pd.DataFrame(rows,columns=["date","R","MAE_R","dir"])

def stats(df,name):
    if df is None or len(df)==0: print(f"{name:34s} no trades");return None
    R=df["R"].values;win=(R>0).mean();exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9);wk=len(R)/NWK
    L=df[df["dir"]>0]["R"];S=df[df["dir"]<0]["R"]
    print(f"{name:34s} n={len(R):4d}({wk:.1f}/wk) win={win*100:4.1f}% expR={exp:+.3f} "
          f"PF={pf:.2f} maxR={R.max():4.1f} | L:{L.mean():+.2f} S:{S.mean():+.2f}")
    return df

if __name__=="__main__":
    print("\n=== XAUUSD 22y ORB session scan (stop=range, EOD, cost$0.40) ===\n")
    for oh in range(1,22):
        stats(orb(open_hr=oh,stop_mode="range",eod_hr=min(oh+7,23)),f"open={oh:02d}h range-stop")
