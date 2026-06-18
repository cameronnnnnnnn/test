import sys, os; sys.path.insert(0, 'ftmo'); os.chdir('/home/user/v4')
import numpy as np, pandas as pd
import research as R, ftmo_sim as F

df = R.load()

def combo(d, p):
    mr = R.sig_meanrev(d, p, 5, 1.0); tr = R.sig_sma_trend(d, p, 10, 40)
    return np.where((mr == 1) & (tr == 1), 1, np.where((mr == -1) & (tr == -1), -1, 0))

print("="*70)
print("1) WALK-FORWARD: tune nothing, just split in/out of sample")
print("="*70)
n = len(df); cut = int(n*0.6)
for label, sub in [("IN  (first 60%, 2021-23)", df.iloc[:cut].reset_index(drop=True)),
                   ("OUT (last 40%, 2024-26)", df.iloc[cut:].reset_index(drop=True))]:
    tr = R.backtest(sub, combo, 1.0)
    R.stats(tr, label)
    mc = F.monte_carlo(tr, 0.0075, n=4000)
    print(f"     MC r=0.75%  PASS={mc['pass']*100:.1f}%  failG={mc['fail_global']*100:.1f}%")

print("\n" + "="*70)
print("2) COST / SLIPPAGE STRESS (full sample, r=0.75%)")
print("="*70)
base = dict(R.COST)
for mult, slip in [(1.0, -1.0), (2.0, -1.0), (3.0, -1.0), (2.0, -1.25)]:
    R.COST = {k: v*mult for k, v in base.items()}
    # patch stop floor to model worse fills on losers
    orig = F.run_attempt
    tr = R.backtest(df, combo, 1.0)
    if slip < -1.0:
        tr = tr.copy(); tr.loc[tr["R"] <= -0.999, "R"] = slip
    mc = F.monte_carlo(tr, 0.0075, n=4000)
    print(f"  cost x{mult}  loserFill={slip}R  expR={tr['R'].mean():+.3f}  PASS={mc['pass']*100:.1f}%  failG={mc['fail_global']*100:.1f}%")
R.COST = base

print("\n" + "="*70)
print("3) PARAMETER SENSITIVITY (full sample, r=0.75%, expR & MC pass)")
print("="*70)
for fast, slow in [(5,30),(10,40),(10,50),(15,50),(20,60)]:
    for zn, zk in [(5,1.0),(5,0.75),(7,1.0)]:
        def c(d,p,fa=fast,sl=slow,n=zn,k=zk):
            mr=R.sig_meanrev(d,p,n,k); t=R.sig_sma_trend(d,p,fa,sl)
            return np.where((mr==1)&(t==1),1,np.where((mr==-1)&(t==-1),-1,0))
        tr=R.backtest(df,c,1.0)
        if len(tr)<50:
            print(f"  sma{fast}/{slow} z{zn}k{zk}: too few"); continue
        mc=F.monte_carlo(tr,0.0075,n=3000)
        print(f"  sma{fast}/{slow} z{zn}k{zk}: n={len(tr):3d} expR={tr['R'].mean():+.3f} PF={(tr['R'][tr['R']>0].sum()/-tr['R'][tr['R']<0].sum()):.2f} PASS={mc['pass']*100:.1f}%")
