"""
Walk-forward robustness: is the edge (and the resulting pass rate) stable across periods,
or is a high pass rate just luck from one favorable stretch? Splits the full trade history
into calendar sub-periods, and for each reports the per-trade edge (with bootstrap CI) and
the MC pass/blow at 0.50% risk (the frontier sweet spot), static floor.
"""
import sys; sys.path.insert(0,'/home/user/v4/ftmo/passopt'); sys.path.insert(0,'/home/user/v4/ftmo')
import numpy as np, pandas as pd
from harness import build_trades, mc, edge_ci

cfg=dict(open_hrs=[15,16], stop_pts=80, tp_R=3.0, side='both')
# rebuild full df of trades with dates
tr,te,df = build_trades(cfg)
df=df.sort_values('date').reset_index(drop=True)

def pool_from(df_sub):
    return [list(zip(g['R'].values,g['MAE'].values)) for _,g in df_sub.groupby(df_sub['date'].dt.normalize())]

# calendar sub-periods (half-years) + the two big halves
edges=[]
periods=[]
for (y0,m0,y1,m1,name) in [
    (2022,10,2023,4,'2022H2'),(2023,4,2023,10,'2023H1'),(2023,10,2024,4,'2023H2'),
    (2024,4,2024,10,'2024H1'),(2024,10,2025,4,'2024H2'),(2025,4,2025,11,'2025H1')]:
    a=pd.Timestamp(y0,m0,1); b=pd.Timestamp(y1,m1,1)
    sub=df[(df['date']>=a)&(df['date']<b)]
    periods.append((name,sub))

print(f"cfg={cfg} | risk 0.50% static floor | per-period walk-forward")
print(f"{'period':<9}{'days':>5}{'trades':>7}{'edgeR':>8}{'90%CI':>20}{'passE':>8}{'blow':>7}{'medD':>6}")
print('-'*70)
for name,sub in periods:
    pool=pool_from(sub)
    mR,lo,hi,n = edge_ci(pool)
    m=mc(pool, 0.005, 'static', horizon=252, N=8000)
    flag='' if lo>0 else '  <-CI incl 0'
    print(f"{name:<9}{len(pool):>5}{n:>7}{mR:>+8.3f}   [{lo:+.3f},{hi:+.3f}]{m['passE']:>7.1f}%{m['blow']:>6.1f}%{m['med']:>6.0f}{flag}")

print("\nInterpretation: if passE swings widely across periods and some CIs include 0, a high")
print("full-sample or single-half pass rate is period-luck, not a robust edge.")
