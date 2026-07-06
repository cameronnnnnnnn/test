"""
Final robustness stress on the winner: vol 0.5-1.0 (causal) + both-sides + 3R TP + 80pt.
1) Does it hold under the STRICTER trailing peak-10% floor (not just static)?
2) Block-bootstrap: stitch random contiguous 120-trade-day blocks (cleaner independent samples
   than heavily-overlapping forward-calendar starts) -> pass/blow under both floors.
Risk levels 0.50% and 0.75%.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from orb_v4 import build_all, orb_v4
DAYS,CTX=build_all()
order=[d[0] for d in DAYS]
CAUSAL={}; prev=np.nan
for day in order:
    cur=CTX.get(day,{}).get('atrpct',np.nan); cc=dict(CTX.get(day,{})); cc['atrpct']=prev; CAUSAL[day]=cc; prev=cur
START=15000.; TARGET=16500.; STATIC=13500.; DDAY=0.03; MIN=4; CONS=0.50

dfs=[]
for hr in (15,16):
    RR,MAE,DTS=orb_v4(DAYS,CAUSAL,with_dates=True,open_hr=hr,range_min=30,stop_pts=80,be_at=1.0,
        trail_k=5.0,tp_R=3.0,cost=2.0,eod_hr=23,rng_filter=True,vol_confirm=True,side='both',atr_regime=(0.5,1.0))
    dfs.append(pd.DataFrame({'date':pd.to_datetime(DTS),'R':RR,'MAE':MAE}))
df=pd.concat(dfs,ignore_index=True).sort_values('date')
DSEQ=[list(zip(g['R'].values,g['MAE'].values)) for _,g in df.groupby(df['date'].dt.normalize())]
ND=len(DSEQ)

def walk_bb(r, floor_mode, rng, H=400):
    """block-bootstrap path: stitch random contiguous 120-day blocks until resolve."""
    eq=START; peak=START; floor=STATIC if floor_mode=='static' else peak*0.9
    dp=[]; td=0; pos_in_block=999; bstart=0
    for s in range(H):
        if pos_in_block>=120: bstart=rng.integers(0,ND); pos_in_block=0
        day=DSEQ[(bstart+pos_in_block)%ND]; pos_in_block+=1
        ds=eq; dl=eq
        for (R,MAE) in day:
            low=eq-r*MAE*eq; dl=min(dl,low)
            if low<=floor: return 'B'
            eq=eq+r*R*eq
            if floor_mode=='trail' and eq>peak: peak=eq; floor=peak*0.9
            if eq<=floor: return 'B'
        td+=1; dp.append(eq-ds)
        if (ds-dl)/ds>=DDAY: return 'B'
        if eq>=TARGET and td>=MIN:
            p=[x for x in dp if x>0]
            if p and max(p)<=CONS*sum(p): return 'P'
    return 'T'

print("Winner: vol 0.5-1.0 causal + both-sides + 3R TP + 80pt | block-bootstrap N=10000\n")
print(f"{'risk':<8}{'floor':<9}{'PASS':>7}{'BLOW':>7}{'timeout':>9}")
print('-'*40)
for rp in [0.5,0.75]:
    for fl in ['static','trail']:
        rng=np.random.default_rng(11)
        out=[walk_bb(rp/100,fl,rng) for _ in range(10000)]
        P=100*out.count('P')/len(out); B=100*out.count('B')/len(out); T=100*out.count('T')/len(out)
        print(f"{rp:<8.2f}{fl:<9}{P:>6.1f}%{B:>6.1f}%{T:>8.1f}%")
    print()
