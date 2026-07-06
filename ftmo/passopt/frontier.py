"""
Risk <-> pass% <-> time frontier for the winning config
(vol>=0.5 + trail 5R + partial 50%@2R->BE + BE@1R, both sessions).
Sweeps risk finely; for each, block-bootstrap 10k under BOTH floors, reporting pass%, blow%,
and MEAN + MEDIAN calendar time-to-pass. Shows how raising risk trades pass% for speed.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np
from evalcfg import build_df, _dayseq, START, TARGET, STATIC, DDAY, MIN, CONS, TOTAL_TD

CFG=dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[0.5,1.0],trail_k=5.0,tp_R=None,
         partial_at=2.0,partial_frac=0.5,partial_be=True)
df=build_df(CFG); DAYS=_dayseq(df); ND=len(DAYS); CAL=TOTAL_TD/ND/21.0  # trade-days -> calendar months

def bb(r, floor_mode, N=10000, seed=11):
    rng=np.random.default_rng(seed); P=B=0; pdays=[]
    for _ in range(N):
        eq=START; peak=START; floor=STATIC if floor_mode=='static' else peak*0.9; dp=[]; td=0; pib=999; bs=0; res='T'
        for s in range(600):
            if pib>=120: bs=rng.integers(0,ND); pib=0
            _,day=DAYS[(bs+pib)%ND]; pib+=1; ds=eq; dl=eq
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
                if p and max(p)<=CONS*sum(p): res='P'; pdays.append(td); break
        if res=='P': P+=1
        elif res=='B': B+=1
    mean=np.mean(pdays)*CAL if pdays else float('nan'); med=np.median(pdays)*CAL if pdays else float('nan')
    return 100*P/N, 100*B/N, mean, med

print("Winner: vol>=0.5 + trail 5R + partial 50%@2R->BE + BE@1R, both sessions | block-bootstrap 10k\n")
print(f"{'risk%':>6} | {'PASS static':>11} {'PASS trail':>10} | {'BLOW trail':>10} | {'avg months':>10} {'med months':>10}")
print('-'*72)
for rp in [0.4,0.5,0.6,0.65,0.7,0.75,0.8,0.85,0.9,1.0,1.1,1.25,1.5,2.0]:
    r=rp/100
    ps,bs_,ms_avg,ms_med=bb(r,'static'); pt,bt,mt_avg,mt_med=bb(r,'trail')
    print(f"{rp:>6.2f} | {ps:>10.1f}% {pt:>9.1f}% | {bt:>9.1f}% | {mt_avg:>9.1f} {mt_med:>9.1f}")
print("\n(avg/med months = calendar time-to-pass on the trailing floor; blow shown for trailing = the binding floor)")
print("Read down: higher risk -> faster (fewer months) but pass% falls & blow% rises. Pick your point.")
