"""
NAS100 INTRADAY engine on real M1. This is where the fat tails live:
a 300pt trend day caught with a 60pt stop = 5R. FX could not do this (spread
ate it); NAS100's 131:1 range/spread ratio is the real test.

Step 1: locate the active (high tick-volume) session from the data itself.
Step 2: opening-range breakout around session open, real M1 fills, ATR/fixed stop,
        exit at session end or trail. Track MAE for the 3% daily rule.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

m=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl")
m["date"]=m["dt"].dt.date
m["hr"]=m["dt"].dt.hour
m["minute"]=m["dt"].dt.hour*60+m["dt"].dt.minute
m["dow"]=m["dt"].dt.dayofweek

# --- locate active session via tick volume by server hour ---
hv=m.groupby("hr")["tv"].mean()
print("avg tick-volume by server hour (find the cash session):")
top=hv.sort_values(ascending=False)
print("  highest-vol hours:", list(top.head(6).index))
print("  " + " ".join(f"{h:02d}:{int(v)}" for h,v in hv.items()))

COST=2.0  # index points, spread+slip per round trip-ish (conservative)

def orb(open_hr, range_min=30, stop_mode="range", stop_pts=60, fixed_stop_frac=0.5,
        target_R=None, trail_R=None, eod_hr=None, cost=COST, side="both"):
    """Opening-range breakout.
       Build [open_hr:00, open_hr:00+range_min) range. Break of high->long, low->short.
       stop_mode 'range': stop = opposite side of range (risk=range size).
                 'fixed': stop = stop_pts.
       Exit: target_R, trailing trail_R (ratchet on close), or end-of-day eod_hr."""
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
        H=sess["high"].values; L=sess["low"].values; C=sess["close"].values
        O=sess["open"].values
        pos=0; entry=0.0; stop_px=0.0; risk=0.0; ext=0.0; exitR=None; mae=0.0
        for i in range(len(sess)):
            if pos==0:
                # breakout trigger (need not be first bar)
                if side in ("both","long") and H[i]>=rhi and O[i]<rhi+ (rhi-rlo):
                    pos=1; entry=max(rhi,O[i])
                    risk=(rhi-rlo) if stop_mode=="range" else stop_pts
                    stop_px=entry-risk; ext=entry
                elif side in ("both","short") and L[i]<=rlo:
                    pos=-1; entry=min(rlo,O[i])
                    risk=(rhi-rlo) if stop_mode=="range" else stop_pts
                    stop_px=entry+risk; ext=entry
                if pos!=0 and (risk<=0 or not np.isfinite(risk)): pos=0
                continue
            # manage open position with this bar's H/L/C
            adv=(entry-L[i]) if pos>0 else (H[i]-entry); mae=max(mae,adv)
            if (pos>0 and L[i]<=stop_px) or (pos<0 and H[i]>=stop_px):
                exitR=(pos*(stop_px-entry)-cost)/risk; break
            ext = max(ext,H[i]) if pos>0 else min(ext,L[i])
            curR=(pos*(C[i]-entry))/risk
            if target_R is not None and curR>=target_R:
                exitR=(pos*(C[i]-entry)-cost)/risk; break
            if trail_R is not None:
                ts=ext - pos*trail_R*risk
                stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
        if pos!=0 and exitR is None:
            exitR=(pos*(C[-1]-entry)-cost)/risk
        if pos!=0:
            rows.append({"date":day,"R":exitR,"MAE_R":max(mae,0)/risk,"dir":pos})
    return pd.DataFrame(rows)

def stats(df,name):
    if df is None or len(df)==0: print(f"{name:40s} no trades"); return None
    R=df["R"].values; win=(R>0).mean(); exp=R.mean()
    pf=R[R>0].sum()/(-R[R<0].sum()+1e-9)
    wk=len(R)/153.0
    L=df[df["dir"]>0]["R"]; S=df[df["dir"]<0]["R"]
    print(f"{name:40s} n={len(R):4d}({wk:.1f}/wk) win={win*100:4.1f}% expR={exp:+.3f} "
          f"PF={pf:.2f} maxR={R.max():4.1f} | L:{L.mean():+.2f} S:{S.mean():+.2f}")
    return df

print("\n=== NAS100 OPENING-RANGE BREAKOUT sweep (real M1 fills, cost=2pt) ===")
print("(testing several session-open hours; range=30m; stop=range; exit EOD)\n")
for oh in [1,2,7,8,9,13,14,15,16]:
    stats(orb(open_hr=oh,range_min=30,stop_mode="range",eod_hr=oh+7),
          f"ORB open={oh:02d}h range30 stop=range EOD")
