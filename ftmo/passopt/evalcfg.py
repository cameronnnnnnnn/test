"""
Batch config evaluator for the FTMO $15k pass-rate search. Backward-compatible with orb_v4;
supports BE, hard TP, trailing, stepped lock, and PARTIAL scale-outs, plus a CAUSAL ATR-regime
gate (prior-day percentile, no lookahead) and per-trade risk %.

evaluate(cfg) -> metrics dict. CLI: python3 evalcfg.py configs.json out.json
Config keys (all optional): open_hrs[list], range_min, stop_pts, be_at, trail_k, tp_R,
  lock_trig, lock_to, partial_at, partial_frac, partial_be, side, atr_regime[lo,hi],
  close_confirm, mom_into, dow_skip, risk_pct(default 0.5).
Metrics: n, edge + 90%CI (full/train/test), and for BOTH floors (static $13,500 & trailing
  peak-10%): contiguous-calendar pass%, WORST start-half%, blow%, ~months; plus block-bootstrap
  pass%. Headline robustness = min(worst_static, worst_trail).
"""
import sys, os, json; sys.path.insert(0,'/home/user/v4/ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4

_DAYS,_CTX=build_all()
_order=[d[0] for d in _DAYS]
_CAUSAL={}; _p=np.nan
for _d in _order:
    _cur=_CTX.get(_d,{}).get('atrpct',np.nan); _cc=dict(_CTX.get(_d,{})); _cc['atrpct']=_p; _CAUSAL[_d]=_cc; _p=_cur
TOTAL_TD=len(_order)
SPLIT=pd.Timestamp('2024-10-01')
START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50

def build_df(cfg):
    hrs=cfg.get('open_hrs',[15,16])
    kw=dict(range_min=cfg.get('range_min',30), stop_pts=cfg.get('stop_pts',80),
        be_at=cfg.get('be_at',1.0), trail_k=cfg.get('trail_k',5.0), tp_R=cfg.get('tp_R',3.0),
        lock_trig=cfg.get('lock_trig',None), lock_to=cfg.get('lock_to',None),
        partial_at=cfg.get('partial_at',None), partial_frac=cfg.get('partial_frac',0.5),
        partial_be=cfg.get('partial_be',True), cost=2.0, eod_hr=cfg.get('eod_hr',23),
        rng_filter=cfg.get('rng_filter',True), vol_confirm=cfg.get('vol_confirm',True),
        side=cfg.get('side','both'), atr_regime=(tuple(cfg['atr_regime']) if cfg.get('atr_regime') else None),
        close_confirm=cfg.get('close_confirm',False), mom_into=cfg.get('mom_into',None),
        dow_skip=cfg.get('dow_skip',None))
    dfs=[]
    for hr in hrs:
        RR,MAE,DTS=orb_v4(_DAYS,_CAUSAL,with_dates=True,open_hr=hr,**kw)
        dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
    return pd.concat(dfs,ignore_index=True).sort_values('date')

def _dayseq(df):
    return [(pd.Timestamp(d),list(zip(g['R'].values,g['MAE'].values))) for d,g in df.groupby(df['date'].dt.normalize())]

def _walk(days,i,r,floor_mode,H=400):
    n=len(days); eq=START; peak=START; floor=STATIC if floor_mode=='static' else peak*0.9; dp=[]; td=0
    for s in range(H):
        _,day=days[(i+s)%n]; ds=eq; dl=eq
        for (R,MAE) in day:
            low=eq-r*MAE*eq
            if low<dl: dl=low
            if low<=floor: return 'B',td+1
            eq=eq+r*R*eq
            if floor_mode=='trail' and eq>peak: peak=eq; floor=peak*0.9
            if eq<=floor: return 'B',td+1
        td+=1; dp.append(eq-ds)
        if (ds-dl)/ds>=DDAY: return 'B',td
        if eq>=TARGET and td>=MIN:
            pos=[x for x in dp if x>0]
            if pos and max(pos)<=CONS*sum(pos): return 'P',td
    return 'T',td

def _contig(days,r,floor_mode):
    res=[(days[i][0],*_walk(days,i,r,floor_mode)) for i in range(len(days))]
    P=100*sum(o=='P' for _,o,_ in res)/len(res); B=100*sum(o=='B' for _,o,_ in res)/len(res)
    def hy(t): return f"{t.year}H{1 if t.month<7 else 2}"
    bh={}
    for d,o,_ in res: bh.setdefault(hy(d),[]).append(o)
    worst=min(100*v.count('P')/len(v) for v in bh.values())
    pdays=[t for _,o,t in res if o=='P']
    months=(np.median(pdays)*TOTAL_TD/len(days)/21) if pdays else float('nan')
    return P,worst,B,months

def _block(days,r,floor_mode,N=6000,seed=11):
    rng=np.random.default_rng(seed); ND=len(days); P=B=0
    for _ in range(N):
        eq=START; peak=START; floor=STATIC if floor_mode=='static' else peak*0.9; dp=[]; td=0; pib=999; bs=0; res='T'
        for s in range(400):
            if pib>=120: bs=rng.integers(0,ND); pib=0
            _,day=days[(bs+pib)%ND]; pib+=1; ds=eq; dl=eq
            for (R,MAE) in day:
                low=eq-r*MAE*eq; dl=min(dl,low)
                if low<=floor: res='B'; break
                eq=eq+r*R*eq
                if floor_mode=='trail' and eq>peak: peak=eq; floor=peak*0.9
                if eq<=floor: res='B'; break
            if res=='B': break
            td+=1; dp.append(eq-ds)
            if (ds-dl)/ds>=DDAY: res='B'; break
            if eq>=TARGET and td>=MIN:
                p=[x for x in dp if x>0]
                if p and max(p)<=CONS*sum(p): res='P'; break
        if res=='P': P+=1
        elif res=='B': B+=1
    return 100*P/N,100*B/N

def _ci(R,seed=1,B=3000):
    if len(R)<20: return (float('nan'),float('nan'),float('nan'))
    rng=np.random.default_rng(seed); n=len(R)
    m=np.array([R[rng.integers(0,n,n)].mean() for _ in range(B)])
    return (float(R.mean()),float(np.percentile(m,5)),float(np.percentile(m,95)))

def evaluate(cfg, quick=True):
    df=build_df(cfg); r=cfg.get('risk_pct',0.5)/100.0
    if len(df)<40: return dict(cfg=cfg,n=len(df),robust=0.0,note='too few trades')
    days=_dayseq(df)
    ps,ws,bs_,ms=_contig(days,r,'static'); pt,wt,bt,mt=_contig(days,r,'trail')
    eF=_ci(df['R'].values); eTr=_ci(df[df['date']<SPLIT]['R'].values); eTe=_ci(df[df['date']>=SPLIT]['R'].values)
    out=dict(cfg=cfg, n=int(len(df)),
        pass_static=round(ps,1), worst_static=round(ws,1), blow_static=round(bs_,1), months=round(ms,1),
        pass_trail=round(pt,1), worst_trail=round(wt,1), blow_trail=round(bt,1),
        robust=round(min(ws,wt),1),
        edge=round(eF[0],3), edge_ci=[round(eF[1],3),round(eF[2],3)],
        edge_train_ci=[round(eTr[1],3),round(eTr[2],3)], edge_test_ci=[round(eTe[1],3),round(eTe[2],3)])
    if not quick:
        bbps,_=_block(days,r,'static'); bbpt,_=_block(days,r,'trail')
        out['bb_static']=round(bbps,1); out['bb_trail']=round(bbpt,1)
    return out

if __name__=='__main__':
    if len(sys.argv)>=3:
        cfgs=json.load(open(sys.argv[1])); out=[evaluate(c) for c in cfgs]
        json.dump(out,open(sys.argv[2],'w'),indent=1); print(f"wrote {len(out)} results to {sys.argv[2]}")
    else:  # smoke test: baseline + a partial variant
        for c in [dict(side='both',tp_R=3.0,risk_pct=0.5),
                  dict(side='both',tp_R=3.0,atr_regime=[0.5,1.0],risk_pct=0.5),
                  dict(side='both',tp_R=None,partial_at=1.5,partial_frac=0.5,partial_be=True,trail_k=3.0,risk_pct=0.5)]:
            m=evaluate(c); print(json.dumps({k:m[k] for k in ['n','pass_static','worst_static','pass_trail','worst_trail','robust','months','edge','edge_ci']}),'  <-',c)
