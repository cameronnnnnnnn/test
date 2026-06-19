"""
Gold breakout is dead (negative every hour, 22y). Test the alternatives for a
ROBUST gold edge that holds across regimes:
  A) DAILY trend-aligned pullback (principled; survived FX/NAS)
  B) DAILY mean-reversion (fade z-score extreme, no trend filter) — gold reverts
  C) INTRADAY fade of the opening-range extreme (inverse of the losing breakout)
Each judged by per-ERA walk-forward (bull/bear/range) + both-sides sign.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from xau20_intraday import DAYS, NWK

# ---------------- DAILY tests ----------------
d=pd.read_pickle("ftmo/xau_full/xau20_daily.pkl").reset_index(drop=True)
o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values
dow=d["date"].dt.dayofweek.values;yr=d["date"].dt.year.values;N=len(d)
s=pd.Series(c)
fast=s.rolling(10).mean().values;slow=s.rolling(40).mean().values
ma5=s.rolling(5).mean().values;sd5=s.rolling(5).std().values
z5=(c-ma5)/(sd5+1e-12)
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
atr=pd.Series(tr).rolling(14).mean().values
COSTD=0.5

def daily_sim(kind,init_atr=1.0,max_hold=1,trail_atr=None):
    rows=[]
    for t in range(40,N-1):
        if dow[t]==4: continue
        if not np.isfinite(atr[t]) or atr[t]<=0: continue
        trend=1 if fast[t]>slow[t] else (-1 if fast[t]<slow[t] else 0)
        if kind=="pullback":
            sig=1 if (z5[t]<-1 and trend==1) else (-1 if (z5[t]>1 and trend==-1) else 0)
        elif kind=="revert":   # fade extreme regardless of trend
            sig=1 if z5[t]<-1.2 else (-1 if z5[t]>1.2 else 0)
        elif kind=="trendbreak":
            sig=1 if (c[t]>fast[t] and trend==1) else (-1 if (c[t]<fast[t] and trend==-1) else 0)
        else: sig=0
        if sig==0: continue
        entry=o[t+1];stop0=atr[t]*init_atr
        stop_px=entry-stop0 if sig>0 else entry+stop0
        ext=entry;exitR=None;mae=0.0
        for k in range(1,max_hold+1):
            ti=t+k
            if ti>=N: break
            hi,lo,cl=h[ti],l[ti],c[ti]
            adv=(entry-lo) if sig>0 else (hi-entry);mae=max(mae,adv)
            if (sig>0 and lo<=stop_px) or (sig<0 and hi>=stop_px):
                exitR=(sig*(stop_px-entry)-COSTD)/stop0;break
            ext=max(ext,hi) if sig>0 else min(ext,lo)
            if trail_atr is not None:
                ts=ext-sig*trail_atr*atr[t]
                stop_px=max(stop_px,ts) if sig>0 else min(stop_px,ts)
            if dow[ti]==4 or k==max_hold:
                exitR=(sig*(cl-entry)-COSTD)/stop0;break
        if exitR is None: exitR=(sig*(c[min(t+max_hold,N-1)]-entry)-COSTD)/stop0
        rows.append({"date":d["date"].iloc[t+1],"R":exitR,"MAE_R":max(mae,0)/stop0,"dir":sig,"yr":yr[t]})
    return pd.DataFrame(rows)

# ---------------- INTRADAY fade ----------------
def fade_orb(open_hr,range_min=30,stop_pts=8.0,target_R=1.0,eod_hr=None,cost=0.40):
    """Inverse of breakout: when price breaks the opening range, FADE it
       (short the high-break / long the low-break), stop beyond, target reversion."""
    if eod_hr is None: eod_hr=min(open_hr+7,23)
    o0=open_hr*60;o1=open_hr*60+range_min;e1=eod_hr*60
    rows=[]
    for day,mn,O,H,L,C in DAYS:
        om=(mn>=o0)&(mn<o1)
        if om.sum()<range_min*0.5: continue
        rhi=H[om].max();rlo=L[om].min();rng=rhi-rlo
        if rng<=0: continue
        sm=(mn>=o1)&(mn<e1)
        if sm.sum()<10: continue
        sH=H[sm];sL=L[sm];sC=C[sm];sO=O[sm]
        pos=0;entry=0.0;stop_px=0.0;risk=stop_pts;exitR=None;mae=0.0
        for i in range(len(sH)):
            if pos==0:
                if sH[i]>=rhi:          # high break -> FADE short
                    pos=-1;entry=max(rhi,sO[i]);stop_px=entry+risk
                elif sL[i]<=rlo:        # low break -> FADE long
                    pos=1;entry=min(rlo,sO[i]);stop_px=entry-risk
                continue
            adv=(entry-sL[i]) if pos>0 else (sH[i]-entry);mae=max(mae,adv)
            if(pos>0 and sL[i]<=stop_px)or(pos<0 and sH[i]>=stop_px):
                exitR=(pos*(stop_px-entry)-cost)/risk;break
            curR=(pos*(sC[i]-entry))/risk
            if curR>=target_R:
                exitR=(pos*(sC[i]-entry)-cost)/risk;break
        if pos!=0 and exitR is None: exitR=(pos*(sC[-1]-entry)-cost)/risk
        if pos!=0: rows.append({"date":day,"R":exitR,"MAE_R":max(mae,0)/risk,"dir":pos,
                                "yr":pd.Timestamp(day).year})
    return pd.DataFrame(rows)

def report(df,name):
    if df is None or len(df)==0: print(f"{name}: no trades");return
    R=df["R"].values
    print(f"\n{name}: n={len(R)} expR={R.mean():+.3f} win={(R>0).mean()*100:.1f}% "
          f"PF={R[R>0].sum()/(-R[R<0].sum()+1e-9):.2f} "
          f"L:{df[df.dir>0]['R'].mean():+.2f} S:{df[df.dir<0]['R'].mean():+.2f}")
    # per-era walk-forward
    for lo,hi,tag in [(2004,2012,"04-11"),(2012,2016,"12-15 bear/range"),
                      (2016,2020,"16-19"),(2020,2023,"20-22"),(2023,2027,"23-26 bull")]:
        sub=df[(df.yr>=lo)&(df.yr<hi)]
        if len(sub): print(f"    {tag:16s} n={len(sub):4d} expR={sub['R'].mean():+.3f} "
                           f"win={(sub['R']>0).mean()*100:4.1f}%")

print("=== A) DAILY trend-pullback ===")
report(daily_sim("pullback"),"daily pullback 1d")
report(daily_sim("pullback",max_hold=5,trail_atr=2.0),"daily pullback swing trail2")
print("\n=== B) DAILY mean-reversion (fade z, no trend) ===")
report(daily_sim("revert"),"daily revert 1d")
print("\n=== C) INTRADAY fade of opening-range break ===")
for oh in (1,12,13,15):
    report(fade_orb(open_hr=oh,stop_pts=8,target_R=1.5),f"fade ORB open={oh}h stop$8 tgt1.5R")
