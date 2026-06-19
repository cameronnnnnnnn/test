"""
STRATEGY LAB: flexible ORB engine + grid search through the full FTMO-rule MC.
Levers: stop size, breakeven trigger, trailing (tight/loose), daily-bias filter,
target cap, session hour, side. Tested on NAS100 (full ~3y) and GOLD (last 10y).
Goal: maximise FTMO pass rate (and minimise blow-up) under all 5 rules.
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

def build_days(m1):
    m=m1.copy()
    m["date"]=pd.to_datetime(m["dt"]).dt.normalize()
    m["minute"]=m["dt"].dt.hour*60+m["dt"].dt.minute
    m["dow"]=m["dt"].dt.dayofweek
    DAYS=[]
    for day,g in m.groupby("date"):
        if g["dow"].iloc[0]>=5: continue
        DAYS.append((pd.Timestamp(day),g["minute"].values,g["open"].values,
                     g["high"].values,g["low"].values,g["close"].values))
    return DAYS

def build_bias(daily):
    d=daily.sort_values("date").reset_index(drop=True)
    sma=d["close"].rolling(20).mean().values; cl=d["close"].values
    b={}
    for i in range(1,len(d)):
        if np.isfinite(sma[i-1]):
            b[pd.Timestamp(d["date"].iloc[i]).normalize()]=1 if cl[i-1]>sma[i-1] else -1
    return b

def orb_v2(DAYS,bias,open_hr=16,range_min=30,stop_pts=60.0,be_at=None,
           trail_k=None,target_R=None,use_bias=False,cost=2.0,eod_hr=23,side="both"):
    o0=open_hr*60;o1=open_hr*60+range_min;e1=eod_hr*60
    rows=[]
    for day,mn,O,H,L,C in DAYS:
        bd=bias.get(day,0)
        allow_long = side in("both","long") and (bd>=0 if use_bias else True)
        allow_short= side in("both","short") and (bd<=0 if use_bias else True)
        om=(mn>=o0)&(mn<o1)
        if om.sum()<range_min*0.5: continue
        rhi=H[om].max();rlo=L[om].min();rng=rhi-rlo
        if rng<=0: continue
        sm=(mn>=o1)&(mn<e1)
        if sm.sum()<10: continue
        sH=H[sm];sL=L[sm];sC=C[sm];sO=O[sm]
        pos=0;entry=0.0;stop_px=0.0;risk=stop_pts;ext=0.0;exitR=None;mae=0.0
        for i in range(len(sH)):
            if pos==0:
                if allow_long and sH[i]>=rhi and sO[i]<rhi+rng:
                    pos=1;entry=max(rhi,sO[i]);stop_px=entry-risk;ext=entry
                elif allow_short and sL[i]<=rlo and sO[i]>rlo-rng:
                    pos=-1;entry=min(rlo,sO[i]);stop_px=entry+risk;ext=entry
                continue
            adv=(entry-sL[i]) if pos>0 else (sH[i]-entry);mae=max(mae,adv)
            if(pos>0 and sL[i]<=stop_px)or(pos<0 and sH[i]>=stop_px):
                exitR=(pos*(stop_px-entry)-cost)/risk;break
            ext=max(ext,sH[i]) if pos>0 else min(ext,sL[i])
            curR=(pos*(sC[i]-entry))/risk
            if be_at is not None and curR>=be_at:
                stop_px=max(stop_px,entry) if pos>0 else min(stop_px,entry)
            if trail_k is not None:
                ts=ext-pos*trail_k*risk
                stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
            if target_R is not None and curR>=target_R:
                exitR=(pos*(sC[i]-entry)-cost)/risk;break
        if pos!=0 and exitR is None: exitR=(pos*(sC[-1]-entry)-cost)/risk
        if pos!=0: rows.append((exitR,max(mae,0)/risk))
    if not rows: return np.array([]),np.array([])
    a=np.array(rows); return a[:,0],a[:,1]

# ---------- FTMO MC (one trade/day, all 5 rules) ----------
START=15000.0;TARGET=1.10*START;GLOBAL=0.905*START
DAILY_BUF=0.028;CONS_PASS=0.50;MIN_DAYS=4
def mc(RR,MAE,r,deadline,n=3000,seed=5):
    if len(RR)<20: return 0.0,1.0
    rng=np.random.default_rng(seed); npass=nfail=0
    L=len(RR)
    for _ in range(n):
        eq=START;dp=[];nd=0;res="TIMEOUT"
        while nd<deadline:
            i=rng.integers(L);R=RR[i];mae=MAE[i];peak=eq
            if r*mae*eq/peak>=DAILY_BUF: pnl=-DAILY_BUF*peak
            else:
                pnl=r*R*eq
                if pnl<-DAILY_BUF*peak: pnl=-DAILY_BUF*peak
            eq+=pnl;nd+=1;dp.append(pnl)
            if eq<=GLOBAL: res="FAIL";break
            if eq>=TARGET and nd>=MIN_DAYS:
                w=[p for p in dp if p>0]
                if w and max(w)<=CONS_PASS*sum(w): res="PASS";break
        if res=="PASS": npass+=1
        elif res=="FAIL": nfail+=1
    return npass/n,nfail/n

if __name__=="__main__":
    # ---- NAS100 ----
    nas=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl")
    nas_daily=pd.read_pickle("ftmo/m1_nas/nas_daily.pkl")
    ND=build_days(nas); NB=build_bias(nas_daily)
    print(f"NAS100: {len(ND)} days (~3y, full available)\n")

    grid=[]
    for stop in (60,):
        for be in (None,1.0):
            for trail in (None,2.0,3.0,1.5):
                for tgt in (None,5.0):
                    for ub in (False,True):
                        grid.append(dict(stop_pts=stop,be_at=be,trail_k=trail,
                                         target_R=tgt,use_bias=ub))
    rows=[]
    for cfg in grid:
        RR,MAE=orb_v2(ND,NB,open_hr=16,cost=2.0,**cfg)
        if len(RR)<20: continue
        p3,b3=mc(RR,MAE,0.015,15); p8,b8=mc(RR,MAE,0.010,40)
        rows.append({**cfg,"n":len(RR),"expR":RR.mean(),"win":(RR>0).mean(),
                     "maxR":RR.max(),"p3":p3,"b3":b3,"p8":p8,"b8":b8})
    R=pd.DataFrame(rows).sort_values("p8",ascending=False)
    pd.set_option("display.width",200,"display.max_columns",20)
    def fmt(x):
        return (f"be={str(x.be_at):>4} trail={str(x.trail_k):>4} tgt={str(x.target_R):>4} "
                f"bias={str(x.use_bias):>5} | expR{x.expR:+.3f} win{x.win*100:4.1f} maxR{x.maxR:4.1f} "
                f"| 3wk P{x.p3*100:4.1f}/B{x.b3*100:4.1f}  8wk P{x.p8*100:4.1f}/B{x.b8*100:4.1f}")
    print("NAS100 ORB combinations (open=16h, stop=60), ranked by 8-week pass:")
    for _,x in R.iterrows(): print("  "+fmt(x))
    R.to_pickle("ftmo/m1_nas/nas_grid.pkl")
