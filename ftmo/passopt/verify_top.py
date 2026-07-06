"""
Adversarial verification of the sweep's top configs. For each:
  (1) block-bootstrap N=10k under BOTH floors across 3 independent seeds -> pass range,
  (2) train/test edge 90% CI,
For the fastest winner, a PERTURBATION PLATEAU: vary vol-threshold, partial level, and risk
+/- and confirm robustness is a broad plateau (not a tuned spike).
"""
import sys, os; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from evalcfg import build_df, _dayseq, _block, _ci, SPLIT

TOP={
 'WINNER vol0.5 tr5 pt2/.5 be1 r0.75': dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[0.5,1.0],trail_k=5.0,tp_R=None,partial_at=2.0,partial_frac=0.5,partial_be=True,risk_pct=0.75),
 'vol0.4 tr5 be1 r0.5':                dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[0.4,1.0],trail_k=5.0,tp_R=None,risk_pct=0.5),
 'vol0.5 tp3 lock2>1 be1 r0.75':       dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[0.5,1.0],tp_R=3.0,lock_trig=2.0,lock_to=1.0,risk_pct=0.75),
 'vol0.5 tp3 be1 r0.5 (plain ref)':    dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[0.5,1.0],tp_R=3.0,risk_pct=0.5),
}
print("(1) BLOCK-BOOTSTRAP 10k x 3 seeds, both floors + train/test edge CI\n")
for name,cfg in TOP.items():
    df=build_df(cfg); days=_dayseq(df); r=cfg['risk_pct']/100
    st=[_block(days,r,'static',N=10000,seed=s)[0] for s in (11,23,37)]
    tr=[_block(days,r,'trail', N=10000,seed=s)[0] for s in (11,23,37)]
    eTr=_ci(df[df['date']<SPLIT]['R'].values); eTe=_ci(df[df['date']>=SPLIT]['R'].values)
    print(f"{name}")
    print(f"   static pass {min(st):.1f}-{max(st):.1f}%   trail pass {min(tr):.1f}-{max(tr):.1f}%   n={len(df)}")
    print(f"   edge train {eTr[0]:+.3f}[{eTr[1]:+.3f},{eTr[2]:+.3f}]  test {eTe[0]:+.3f}[{eTe[1]:+.3f},{eTe[2]:+.3f}]\n")

print("(2) PERTURBATION PLATEAU around the WINNER (block-bootstrap trailing floor = the harder one)")
print(f"   {'volLo':>6}{'partR':>7}{'risk%':>7}{'staticP':>9}{'trailP':>8}{'months(contig)':>16}")
from evalcfg import evaluate
for vlo in [0.45,0.5,0.55]:
    for pr in [1.75,2.0,2.25]:
        for rk in [0.65,0.75,0.85]:
            c=dict(side='both',open_hrs=[15,16],be_at=1.0,atr_regime=[vlo,1.0],trail_k=5.0,tp_R=None,
                   partial_at=pr,partial_frac=0.5,partial_be=True,risk_pct=rk)
            m=evaluate(c,quick=False)
            print(f"   {vlo:>6.2f}{pr:>7.2f}{rk:>7.2f}{m['bb_static']:>8.1f}%{m['bb_trail']:>7.1f}%{m['months']:>13.1f}")
