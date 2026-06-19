"""
Extended NAS100 ORB engine with 10 creative improvement levers, each toggleable,
so every combination can be searched through the full FTMO-rule Monte Carlo.

The 10 improvements:
  1 rng_filter   : skip days whose opening range is <0.5x or >2x its trailing median
                   (avoid dead-chop and already-exhausted days)
  2 early_break  : only take breakouts that fire within N min of the range close
                   (early breaks trend; late ones fade)
  3 retest       : enter on a pullback BACK to the level after the break (better fill)
  4 atr_stop     : stop = k * daily ATR instead of fixed 60 (volatility-adaptive)
  5 range_stop   : stop = opening-range width (self-adaptive risk)
  6 partial      : scale half off at +2R, trail the rest (smooths equity / consistency)
  7 reentry      : if the first breakout stops out, allow ONE re-entry on a later break
  8 vol_confirm  : require breakout bar tick-volume > trailing session average
  9 gap_filter   : long only if session opened above prior-day close (and vice-versa)
 10 anti_streak  : [MC] cut risk after consecutive losing days, restore after a win
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

# ---- build per-day arrays WITH tick volume + context ----
def build_all():
    m=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl")
    m["date"]=m["dt"].dt.normalize(); m["minute"]=m["dt"].dt.hour*60+m["dt"].dt.minute
    m["dow"]=m["dt"].dt.dayofweek
    d=pd.read_pickle("ftmo/m1_nas/nas_daily.pkl").sort_values("date").reset_index(drop=True)
    c=d["close"].values; h=d["high"].values; l=d["low"].values
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    ctx={}
    for i in range(len(d)):
        key=pd.Timestamp(d["date"].iloc[i]).normalize()
        ctx[key]={"atr":atr[i] if np.isfinite(atr[i]) else np.nan,
                  "prevclose":c[i-1] if i>0 else np.nan}
    DAYS=[]
    for day,g in m.groupby("date"):
        if g["dow"].iloc[0]>=5: continue
        DAYS.append((pd.Timestamp(day),g["minute"].values,g["open"].values,
                     g["high"].values,g["low"].values,g["close"].values,g["tv"].values))
    return DAYS,ctx

def orb_v3(DAYS,ctx,open_hr=16,range_min=30,stop_pts=60.0,be_at=1.0,trail_k=3.0,
           cost=2.0,eod_hr=23,
           rng_filter=False,early_break=None,retest=False,atr_stop=None,
           range_stop=False,partial=None,reentry=False,vol_confirm=False,
           gap_filter=False,with_dates=False):
    o0=open_hr*60;o1=open_hr*60+range_min;e1=eod_hr*60
    # trailing median of opening-range size for rng_filter
    rsz=[]
    for day,mn,O,H,L,C,V in DAYS:
        om=(mn>=o0)&(mn<o1)
        rsz.append(H[om].max()-L[om].min() if om.any() else np.nan)
    rsz=np.array(rsz); roll_med=pd.Series(rsz).rolling(40,min_periods=10).median().shift(1).values

    rows=[]
    for di,(day,mn,O,H,L,C,V) in enumerate(DAYS):
        cx=ctx.get(day,{})
        om=(mn>=o0)&(mn<o1)
        if om.sum()<range_min*0.5: continue
        rhi=H[om].max();rlo=L[om].min();rng=rhi-rlo
        if rng<=0: continue
        if rng_filter and np.isfinite(roll_med[di]) and roll_med[di]>0:
            if rng<0.5*roll_med[di] or rng>2.0*roll_med[di]: continue
        # stop size
        if atr_stop is not None and np.isfinite(cx.get("atr",np.nan)):
            risk=atr_stop*cx["atr"]
        elif range_stop:
            risk=rng
        else:
            risk=stop_pts
        if risk<=0: continue
        sm=(mn>=o1)&(mn<e1)
        if sm.sum()<10: continue
        idx=np.where(sm)[0]
        sH=H[idx];sL=L[idx];sC=C[idx];sO=O[idx];sV=V[idx];sMn=mn[idx]
        volavg=np.nanmean(V[(mn>=o0)&(mn<o1)]) if vol_confirm else 0
        pc=cx.get("prevclose",np.nan); sess_open=O[om][0] if om.any() else np.nan
        gap_long_ok = (not gap_filter) or (np.isfinite(pc) and sess_open>=pc)
        gap_short_ok= (not gap_filter) or (np.isfinite(pc) and sess_open< pc)

        attempts = 2 if reentry else 1
        used_from=0
        for _att in range(attempts):
            pos=0;entry=0.0;stop_px=0.0;ext=0.0;exitR=None;mae=0.0;booked=False
            pend=0; exit_k=len(sH)-1
            for k in range(used_from,len(sH)):
                if pos==0:
                    longsig = sH[k]>=rhi and sO[k]<rhi+rng and gap_long_ok
                    shortsig= sL[k]<=rlo and sO[k]>rlo-rng and gap_short_ok
                    if early_break is not None and (sMn[k]-o1)>early_break:
                        longsig=shortsig=False
                    if vol_confirm and sV[k]<=volavg:
                        longsig=shortsig=False
                    if retest:
                        if pend==0:
                            if longsig: pend=1
                            elif shortsig: pend=-1
                            continue
                        if pend==1 and sL[k]<=rhi:   pos=1;entry=rhi
                        elif pend==-1 and sH[k]>=rlo: pos=-1;entry=rlo
                        else: continue
                    else:
                        if longsig: pos=1;entry=max(rhi,sO[k])
                        elif shortsig: pos=-1;entry=min(rlo,sO[k])
                        else: continue
                    stop_px=entry-risk if pos>0 else entry+risk; ext=entry; entry_k=k
                    continue
                adv=(entry-sL[k]) if pos>0 else (sH[k]-entry); mae=max(mae,adv)
                if (pos>0 and sL[k]<=stop_px) or (pos<0 and sH[k]>=stop_px):
                    exitR=(pos*(stop_px-entry)-cost)/risk; exit_k=k; break
                ext=max(ext,sH[k]) if pos>0 else min(ext,sL[k])
                curR=(pos*(sC[k]-entry))/risk
                if partial is not None and curR>=partial and not booked:
                    booked=True                      # half banked at +partial; rest -> BE
                    stop_px=max(stop_px,entry) if pos>0 else min(stop_px,entry)
                if be_at is not None and curR>=be_at:
                    stop_px=max(stop_px,entry) if pos>0 else min(stop_px,entry)
                if trail_k is not None:
                    ts=ext-pos*trail_k*risk
                    stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
            if pos==0: break                         # no breakout this attempt
            if exitR is None:
                exitR=(pos*(sC[-1]-entry)-cost)/risk; exit_k=len(sH)-1
            # partial only credited if it actually triggered; record EVERY trade taken
            rfull = (0.5*partial + 0.5*exitR) if (partial is not None and booked) else exitR
            rows.append((rfull,max(mae,0)/risk,day))
            if exitR>0: break                        # winner: stop for the day
            used_from=exit_k+1                       # loser: allow ONE re-entry after exit
    if not rows:
        return (np.array([]),np.array([]),[]) if with_dates else (np.array([]),np.array([]))
    R=np.array([x[0] for x in rows]); M=np.array([x[1] for x in rows])
    if with_dates: return R,M,[x[2] for x in rows]
    return R,M

# ---- FTMO MC with optional anti-streak risk scaling (#10) ----
START=15000.0;TARGET=1.10*START;GLOBAL=0.905*START
DAILY_BUF=0.028;CONS_PASS=0.50;MIN_DAYS=4
def mc(RR,MAE,r,deadline,n=6000,seed=5,anti_streak=False):
    if len(RR)<20: return 0.0,1.0
    rng=np.random.default_rng(seed); npass=nfail=0; L=len(RR)
    for _ in range(n):
        eq=START;dp=[];nd=0;res="TIMEOUT";losses=0
        while nd<deadline:
            rr=r
            if anti_streak and losses>=2: rr=r*0.5    # de-risk in a drawdown streak
            i=rng.integers(L);R=RR[i];mae=MAE[i];peak=eq
            if rr*mae*eq/peak>=DAILY_BUF: pnl=-DAILY_BUF*peak
            else:
                pnl=rr*R*eq
                if pnl<-DAILY_BUF*peak: pnl=-DAILY_BUF*peak
            eq+=pnl;nd+=1;dp.append(pnl)
            losses = losses+1 if R<=0 else 0
            if eq<=GLOBAL: res="FAIL";break
            if eq>=TARGET and nd>=MIN_DAYS:
                w=[p for p in dp if p>0]
                if w and max(w)<=CONS_PASS*sum(w): res="PASS";break
        if res=="PASS": npass+=1
        elif res=="FAIL": nfail+=1
    return npass/n,nfail/n
