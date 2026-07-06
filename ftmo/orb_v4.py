"""
orb_v4: 10 NEW creative levers on top of the validated base
(open16, range30, stop60, BE@1R, trail5R, range-filter + vol-confirm ON).

The 10 new ideas:
  1 vwap_filter    : long only above session VWAP, short only below (institutional ref)
  2 close_confirm  : breakout bar must CLOSE beyond the level (not just wick) -> fewer fakeouts
  3 overnight_conf : breakout level must also clear the pre-US (10-16h) high/low (confluence)
  4 dow_skip       : drop a weekday (Mon..Fri) if it is statistically weak
  5 atr_regime     : only trade when daily ATR percentile is in a band (skip dead vol)
  6 mom_into       : require momentum into the level (last N session closes trending in dir)
  7 side           : asymmetric direction (long-only / short-only) since long edge is bigger
  8 pyramid        : add a 2nd unit at +2R on runners (anti-martingale scale-in)
  9 chandelier     : trail by k*ATR(daily) instead of R-multiples
 10 fail_rev       : if the first breakout stops out, take the OPPOSITE break (fade failure)

Plus a STOP-SIZE sweep (40..120 pt and ATR-based).
"""
import sys, os; sys.path.insert(0,'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd

def build_all():
    m=pd.read_pickle("ftmo/m1_nas/nas_m1.pkl")
    m["date"]=m["dt"].dt.normalize(); m["minute"]=m["dt"].dt.hour*60+m["dt"].dt.minute
    m["dow"]=m["dt"].dt.dayofweek
    d=pd.read_pickle("ftmo/m1_nas/nas_daily.pkl").sort_values("date").reset_index(drop=True)
    c=d["close"].values; h=d["high"].values; l=d["low"].values
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).rolling(14).mean().values
    atrpct=pd.Series(atr).rolling(120,min_periods=30).rank(pct=True).values  # ATR regime percentile
    ctx={}
    for i in range(len(d)):
        k=pd.Timestamp(d["date"].iloc[i]).normalize()
        ctx[k]={"atr":atr[i] if np.isfinite(atr[i]) else np.nan,
                "atrpct":atrpct[i] if np.isfinite(atrpct[i]) else np.nan,
                "prevclose":c[i-1] if i>0 else np.nan}
    DAYS=[]
    for day,g in m.groupby("date"):
        if g["dow"].iloc[0]>=5: continue
        DAYS.append((pd.Timestamp(day),g["minute"].values,g["open"].values,
                     g["high"].values,g["low"].values,g["close"].values,g["tv"].values))
    return DAYS,ctx

def orb_v4(DAYS,ctx,open_hr=16,range_min=30,stop_pts=60.0,be_at=1.0,trail_k=5.0,
           cost=2.0,eod_hr=23, atr_stop=None, tp_R=None, lock_trig=None, lock_to=None,
           partial_at=None, partial_frac=0.5, partial_be=True,
           # base validated filters (kept ON):
           rng_filter=True, vol_confirm=True,
           # the 10 NEW levers:
           vwap_filter=False, close_confirm=False, overnight_conf=False, dow_skip=None,
           atr_regime=None, mom_into=None, side="both", pyramid=False, chandelier=None,
           fail_rev=False, overnight_hours=6, with_dates=False):
    o0=open_hr*60; o1=open_hr*60+range_min; e1=eod_hr*60; preS=(open_hr-overnight_hours)*60
    # trailing median of opening-range size
    rsz=[]
    for day,mn,O,H,L,C,V in DAYS:
        om=(mn>=o0)&(mn<o1); rsz.append(H[om].max()-L[om].min() if om.any() else np.nan)
    roll_med=pd.Series(np.array(rsz)).rolling(40,min_periods=10).median().shift(1).values
    rows=[]
    for di,(day,mn,O,H,L,C,V) in enumerate(DAYS):
        cx=ctx.get(day,{})
        if dow_skip is not None and day.dayofweek in dow_skip: continue
        if atr_regime is not None:
            ap=cx.get("atrpct",np.nan)
            if not (np.isfinite(ap) and atr_regime[0]<=ap<=atr_regime[1]): continue
        om=(mn>=o0)&(mn<o1)
        if om.sum()<range_min*0.5: continue
        rhi=H[om].max(); rlo=L[om].min(); rng=rhi-rlo
        if rng<=0: continue
        if rng_filter and np.isfinite(roll_med[di]) and roll_med[di]>0:
            if rng<0.5*roll_med[di] or rng>2.0*roll_med[di]: continue
        risk = (atr_stop*cx["atr"]) if (atr_stop is not None and np.isfinite(cx.get("atr",np.nan))) else stop_pts
        if risk<=0: continue
        # pre-US range for confluence
        preHi=preLo=np.nan
        if overnight_conf:
            pm=(mn>=preS)&(mn<o0)
            if pm.any(): preHi=H[pm].max(); preLo=L[pm].min()
        sm=(mn>=o1)&(mn<e1)
        if sm.sum()<10: continue
        idx=np.where(sm)[0]
        sH=H[idx];sL=L[idx];sC=C[idx];sO=O[idx];sV=V[idx];sMn=mn[idx]
        volavg=np.nanmean(V[om]) if vol_confirm else 0
        # session VWAP
        if vwap_filter:
            tp=(sH+sL+sC)/3.0; cv=np.cumsum(sV)+1e-9; vwap=np.cumsum(tp*sV)/cv
        atrd=cx.get("atr",np.nan)
        attempts=2 if fail_rev else 1; used_from=0
        for att in range(attempts):
            want = side
            if fail_rev and att==1: want = "flip"  # opposite of first signal
            pos=0;entry=0.0;stop_px=0.0;ext=0.0;exitR=None;mae=0.0
            pyr=False; entry2=0.0; first_dir=0; partial_done=False
            for k in range(used_from,len(sH)):
                if pos==0:
                    Lc = sC[k]>=rhi if close_confirm else sH[k]>=rhi
                    Sc = sC[k]<=rlo if close_confirm else sL[k]<=rlo
                    Lc = Lc and sO[k]<rhi+rng
                    Sc = Sc and sO[k]>rlo-rng
                    if vol_confirm: Lc=Lc and sV[k]>volavg; Sc=Sc and sV[k]>volavg
                    if vwap_filter:
                        px=sC[k] if close_confirm else rhi
                        Lc=Lc and px>vwap[k]; Sc=Sc and (sC[k] if close_confirm else rlo)<vwap[k]
                    if overnight_conf and np.isfinite(preHi):
                        Lc=Lc and rhi>=preHi; Sc=Sc and rlo<=preLo
                    if mom_into is not None and k>=mom_into:
                        up=sC[k]-sC[k-mom_into]; Lc=Lc and up>0; Sc=Sc and up<0
                    # direction gating (side / fail_rev flip)
                    if want=="long": Sc=False
                    elif want=="short": Lc=False
                    elif want=="flip":
                        if first_dir>0: Lc=False        # first was long -> only take short now
                        elif first_dir<0: Sc=False
                    if Lc:
                        pos=1; entry=(sC[k] if close_confirm else max(rhi,sO[k]))
                    elif Sc:
                        pos=-1; entry=(sC[k] if close_confirm else min(rlo,sO[k]))
                    else: continue
                    stop_px=entry-risk if pos>0 else entry+risk; ext=entry
                    if att==0: first_dir=pos
                    continue
                adv=(entry-sL[k]) if pos>0 else (sH[k]-entry); mae=max(mae,adv)
                if (pos>0 and sL[k]<=stop_px) or (pos<0 and sH[k]>=stop_px):
                    exitR=(pos*(stop_px-entry))/risk; exit_k=k; break
                if tp_R is not None:   # hard take-profit (stop checked first = conservative on huge bars)
                    tp_px=entry+pos*tp_R*risk
                    if (pos>0 and sH[k]>=tp_px) or (pos<0 and sL[k]<=tp_px):
                        exitR=tp_R; exit_k=k; break
                if partial_at is not None and not partial_done:   # scale out partial_frac at +partial_at R
                    pp_px=entry+pos*partial_at*risk
                    if (pos>0 and sH[k]>=pp_px) or (pos<0 and sL[k]<=pp_px):
                        partial_done=True
                        if partial_be: stop_px=max(stop_px,entry) if pos>0 else min(stop_px,entry)
                ext=max(ext,sH[k]) if pos>0 else min(ext,sL[k])
                curR=(pos*(sC[k]-entry))/risk
                if pyramid and not pyr and curR>=2.0:
                    pyr=True; entry2=entry+pos*2*risk
                if be_at is not None and curR>=be_at:
                    stop_px=max(stop_px,entry) if pos>0 else min(stop_px,entry)
                if lock_trig is not None:   # stepped lock: once FE reaches lock_trig*R, lock stop at lock_to*R
                    extR=(pos*(ext-entry))/risk
                    if extR>=lock_trig:
                        lp=entry+pos*lock_to*risk
                        stop_px=max(stop_px,lp) if pos>0 else min(stop_px,lp)
                if chandelier is not None and np.isfinite(atrd):
                    ts=ext-pos*chandelier*atrd
                    stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
                elif trail_k is not None:
                    ts=ext-pos*trail_k*risk
                    stop_px=max(stop_px,ts) if pos>0 else min(stop_px,ts)
            else:
                exit_k=len(sH)-1
            if pos==0:
                if not fail_rev: break
                else: continue
            if exitR is None: exitR=(pos*(sC[-1]-entry))/risk
            if partial_at is not None and partial_done:   # blend booked partial + remaining runner
                grossR=partial_frac*partial_at + (1-partial_frac)*exitR
                totR=grossR - cost/risk*(1+partial_frac)
            else:
                units=2 if pyr else 1
                totR=exitR + (exitR-2 if pyr else 0) - cost/risk*units
            rows.append((totR,max(mae,0)/risk,day,pos))
            if (exitR>0 or partial_done): break
            used_from=exit_k+1
            if not fail_rev: break
    if not rows:
        return (np.array([]),np.array([]),[]) if with_dates else (np.array([]),np.array([]))
    R=np.array([x[0] for x in rows]); M=np.array([x[1] for x in rows])
    if with_dates: return R,M,[x[2] for x in rows]
    return R,M

# ---- trailing-DD MC (raw, 1.1% by default) reporting pass% / blow% ----
START=15000.0; TARGET=1.10*START; TRAIL=0.10*START; MIN_DAYS=4; CONS=0.50
def mc(RR,MAE,r=0.011,N=4000,max_steps=200,seed=7):
    if len(RR)<20: return 0.0,1.0
    rng=np.random.default_rng(seed); np_=nb=0
    for _ in range(N):
        eq=START;peak=START;floor=START-TRAIL;dp=[];n=0;res="TO"
        while n<max_steps:
            i=rng.integers(len(RR));R=RR[i];mae=MAE[i];eb=eq
            if eb-r*mae*eb<=floor: res="B";break
            eq=eb+r*R*eb;n+=1;dp.append(eq-eb)
            if eq<=floor: res="B";break
            if eq>peak: peak=eq;floor=peak-TRAIL
            if eq>=TARGET and n>=MIN_DAYS:
                w=[p for p in dp if p>0]
                if w and max(w)<=CONS*sum(w): res="P";break
        if res=="P": np_+=1
        elif res=="B": nb+=1
    return np_/N, nb/N
