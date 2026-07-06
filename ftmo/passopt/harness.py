"""
Pass-rate optimization harness for the FTMO $15k 1-Step Challenge.
- TRAIN = trades dated < 2024-10-01 ; TEST (OOS) = trades dated >= 2024-10-01.
- Indicators (rolling range median, ATR pct) are computed on the FULL series with .shift(1),
  so splitting the resulting trades by date introduces NO lookahead.
- MC: fresh $15,000 account, day-bootstrap resampling from the chosen pool, FTMO rules.
  Static floor $13,500 (primary) or trailing peak-10% (stress). No daily-limit-only failures
  are ignored. Consistency = best day <= 50% of positive-day sum, dilutable.
Reusable: build_trades(cfg) once (R-multiples are risk-independent), sweep risk in the MC.
"""
import sys, os; sys.path.insert(0,'/home/user/v4/ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

_DAYS, _CTX = build_all()
SPLIT = pd.Timestamp('2024-10-01')

def build_trades(cfg):
    """cfg: dict with keys open_hrs(list), stop_pts, tp_R, be_at, trail_k, side, +orb_v4 kwargs.
    Returns (train_days, test_days): each a list of days, each day = list of (R,MAE)."""
    hrs = cfg.get('open_hrs',[15,16])
    kw = dict(range_min=cfg.get('range_min',30), stop_pts=cfg.get('stop_pts',80),
              be_at=cfg.get('be_at',1.0), trail_k=cfg.get('trail_k',5.0), tp_R=cfg.get('tp_R',3.0),
              cost=2.0, eod_hr=cfg.get('eod_hr',23), rng_filter=cfg.get('rng_filter',True),
              vol_confirm=cfg.get('vol_confirm',True), side=cfg.get('side','both'),
              atr_regime=cfg.get('atr_regime',None), atr_stop=cfg.get('atr_stop',None),
              lock_trig=cfg.get('lock_trig',None), lock_to=cfg.get('lock_to',None),
              dow_skip=cfg.get('dow_skip',None), close_confirm=cfg.get('close_confirm',False))
    dfs=[]
    for hr in hrs:
        RR,MAE,DTS = orb_v4(_DAYS,_CTX,with_dates=True,open_hr=hr,**kw)
        dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
    df = pd.concat(dfs,ignore_index=True)
    tr={}; te={}
    for d,g in df.groupby(df['date'].dt.normalize()):
        rec=list(zip(g['R'].values,g['MAE'].values))
        (tr if pd.Timestamp(d)<SPLIT else te)[pd.Timestamp(d)]=rec
    return list(tr.values()), list(te.values()), df

START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50

def mc(pool, r, floor_mode='static', horizon=252, N=10000, seed=7):
    if len(pool)<10: return dict(passE=0,pass63=0,blow=100,med=np.nan,mean=np.nan)
    rng=np.random.default_rng(seed)
    idx=rng.integers(0,len(pool),size=(N,horizon))
    npass=nblow=0; pdays=[]
    for k in range(N):
        eq=START; peak=START
        floor=STATIC if floor_mode=='static' else peak*0.9
        daypnl=[]; td=0; res='T'
        row=idx[k]
        for s in range(horizon):
            day=pool[row[s]]; ds=eq; dl=eq
            for (R,MAE) in day:
                low=eq-r*MAE*eq
                if low<dl: dl=low
                if low<=floor: res='B'; break
                eq=eq+r*R*eq
                if floor_mode=='trail' and eq>peak: peak=eq; floor=peak*0.9
                if eq<=floor: res='B'; break
            if res=='B': break
            td+=1; daypnl.append(eq-ds)
            if (ds-dl)/ds>=DDAY: res='B'; break
            if eq>=TARGET and td>=MIN:
                pos=[x for x in daypnl if x>0]
                if pos and max(pos)<=CONS*sum(pos): res='P'; pdays.append(td); break
        if res=='P': npass+=1
        elif res=='B': nblow+=1
    pe=100*npass/N
    p63=100*sum(1 for d in pdays if d<=63)/N
    return dict(passE=pe, pass63=p63, blow=100*nblow/N,
                med=(np.median(pdays) if pdays else np.nan),
                mean=(np.mean(pdays) if pdays else np.nan))

def edge_ci(days_pool, seed=1, B=5000):
    R=np.array([r for day in days_pool for (r,_) in day])
    if len(R)<20: return (np.nan,np.nan,np.nan,0)
    rng=np.random.default_rng(seed); n=len(R)
    m=np.array([R[rng.integers(0,n,n)].mean() for _ in range(B)])
    return (R.mean(), np.percentile(m,5), np.percentile(m,95), len(R))

if __name__=='__main__':
    cfg=dict(open_hrs=[15,16], stop_pts=80, tp_R=3.0, side='both')
    tr,te,df = build_trades(cfg)
    print(f"baseline cfg={cfg}")
    print(f"trades: train {sum(len(d) for d in tr)} ({len(tr)} days) | test {sum(len(d) for d in te)} ({len(te)} days)")
    mR,lo,hi,ntr = edge_ci(tr); teR,tlo,thi,nte = edge_ci(te)
    print(f"TRAIN edge {mR:+.3f} 90%CI[{lo:+.3f},{hi:+.3f}]  | TEST edge {teR:+.3f} 90%CI[{tlo:+.3f},{thi:+.3f}]")
    print(f"\n{'risk%':<7}{'set':<6}{'floor':<8}{'passE':>7}{'pass63':>8}{'blow':>7}{'medD':>6}{'meanD':>7}")
    print('-'*56)
    for rp in [1.25,1.0,0.75,0.5,0.35,0.25,0.15,0.10]:
        for setn,pool in [('TRAIN',tr),('TEST',te)]:
            for fl in ['static','trail']:
                m=mc(pool, rp/100, fl)
                print(f"{rp:<7.2f}{setn:<6}{fl:<8}{m['passE']:>6.1f}%{m['pass63']:>7.1f}%{m['blow']:>6.1f}%{m['med']:>6.0f}{m['mean']:>7.1f}")
        print()
