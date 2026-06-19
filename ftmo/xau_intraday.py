"""
XAUUSD intraday ORB — same validated engine as NAS100, gold cost in $.
CAVEATS (loud): 6.8-month sample, +40% one-way bull run. Long-vs-short split and
walk-forward are the honesty tells; treat results as optimistic upper bounds.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

m=pd.read_pickle("ftmo/m1_nas/xau_m1.pkl")
m["date"]=m["dt"].dt.date; m["hr"]=m["dt"].dt.hour
m["minute"]=m["dt"].dt.hour*60+m["dt"].dt.minute; m["dow"]=m["dt"].dt.dayofweek
COST=0.40  # $ spread+slip per trade (retail gold ~0.2-0.5); stressed later
NWK=148/5  # ~weeks of data

def orb(open_hr,range_min=30,stop_mode="fixed",stop_pts=8.0,target_R=None,
        trail_R=None,eod_hr=None,cost=COST,side="both"):
    if eod_hr is None: eod_hr=open_hr+7
    rows=[]
    for day,g in m.groupby("date"):
        if g["dow"].iloc[0]>=5: continue
        g=g.sort_values("dt")
        op=g[(g["hr"]>=open_hr)&(g["minute"]<open_hr*60+range_min)]
        if len(op)<range_min*0.5: continue
        rhi=op["high"].max(); rlo=op["low"].min()
        sess=g[(g["minute"]>=open_hr*60+range_min)&(g["hr"]<eod_hr)]
        if len(sess)<10: continue
        H=sess["high"].values;L=sess["low"].values;C=sess["close"].values;O=sess["open"].values
        pos=0;entry=0.0;stop_px=0.0;risk=0.0;ext=0.0;exitR=None;mae=0.0
        for i in range(len(sess)):
            if pos==0:
                if side in("both","long") and H[i]>=rhi and O[i]<rhi+(rhi-rlo):
                    pos=1;entry=max(rhi,O[i]);risk=(rhi-rlo) if stop_mode=="range" else stop_pts
                    stop_px=entry-risk;ext=entry
                elif side in("both","short") and L[i]<=rlo:
                    pos=-1;entry=min(rlo,O[i]);risk=(rhi-rlo) if stop_mode=="range" else stop_pts
                    stop_px=entry+risk;ext=entry
                if pos!=0 and(risk<=0 or not np.isfinite(risk)):pos=0
                continue
            adv=(entry-L[i]) if pos>0 else (H[i]-entry);mae=max(mae,adv)
            if(pos>0 and L[i]<=stop_px)or(pos<0 and H[i]>=stop_px):
                exitR=(pos*(stop_px-entry)-cost)/risk;break
            ext=max(ext,H[i]) if pos>0 else min(ext,L[i])
            curR=(pos*(C[i]-entry))/risk
            if target_R is not None and curR>=target_R:
                exitR=(pos*(C[i]-entry)-cost)/risk;break
            if trail_R is not None:
                ts=ext-pos*trail_R*risk
                stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
        if pos!=0 and exitR is None: exitR=(pos*(C[-1]-entry)-cost)/risk
        if pos!=0: rows.append({"date":day,"R":exitR,"MAE_R":max(mae,0)/risk,"dir":pos})
    return pd.DataFrame(rows)

def stats(df,name):
    if df is None or len(df)==0: print(f"{name:36s} no trades");return None
    R=df["R"].values;win=(R>0).mean();exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9);wk=len(R)/NWK
    L=df[df["dir"]>0]["R"];S=df[df["dir"]<0]["R"]
    print(f"{name:36s} n={len(R):3d}({wk:.1f}/wk) win={win*100:4.1f}% expR={exp:+.3f} "
          f"PF={pf:.2f} maxR={R.max():4.1f} | L:{L.mean():+.2f} S:{S.mean():+.2f}")
    return df

if __name__=="__main__":
    print("XAUUSD ORB session scan (real M1, cost=$0.40, range=30m, stop=$8)\n")
    for oh in [1,7,8,13,14,15,16,17,18]:
        stats(orb(open_hr=oh,eod_hr=min(oh+7,23)),f"open={oh:02d}h stop$8 EOD")
    print("\nstop-size sweep on best US-session hour (17h):")
    for sp in (5,8,12,20):
        stats(orb(open_hr=17,stop_pts=sp,trail_R=3.0,eod_hr=23),f"open17 stop${sp} trail3R")
