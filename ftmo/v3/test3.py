"""v3/test3.py — backtest new signals, rank by 4-week FTMO pass. cost 3pt."""
import numpy as np, strategies as S, engine, ftmo, data, sig3
from run import build_days
from engine import ExitSpec

COST=3.0; RISKS=[0.0075,0.01,0.0125,0.015,0.02,0.025]
def score(name, orders, df, ad):
    tr=engine.simulate(df,orders,cost_pts=COST)
    if len(tr)<60: print(f"  {name:26s} only {len(tr)} trades"); return None
    es=engine.edge_stats(tr); days=build_days(tr,ad)
    def mp(T):
        res=[(r,ftmo.run_mc(days,r,T,n_paths=25000,seed=5)) for r in RISKS]
        return max(res,key=lambda x:x[1]['pass_rate'])
    m3,m4,m8=mp(15),mp(20),mp(40)
    print(f"  {name:26s} n={es['n']:4d} {es['n']/(len(ad)/5):4.1f}/wk WR={es['wr']*100:4.1f}% expR={es['expR']:+.3f} | "
          f"3wk {m3[1]['pass_rate']*100:4.1f}/{m3[1]['blow_rate']*100:3.0f}  "
          f"4wk {m4[1]['pass_rate']*100:4.1f}/{m4[1]['blow_rate']*100:3.0f} (r{m4[0]*100:.2f})  "
          f"8wk {m8[1]['pass_rate']*100:4.1f}/{m8[1]['blow_rate']*100:3.0f}")
    return (name, es, m4[1]['pass_rate'])

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df['date'].unique()))
    tp4=ExitSpec(tp_R=4.0); trl=ExitSpec(trail_R=4.0)
    print("="*120); print("NEW SIGNALS (v3), cost 3pt, ranked focus = 4-week pass"); print("="*120)
    res=[]
    for nm,o in [
        ("gap-cont tp4",   sig3.gap(df, gap_min=20, mode="cont", spec=tp4)),
        ("gap-fade tp4",   sig3.gap(df, gap_min=20, mode="fade", spec=tp4)),
        ("gap-cont trail4",sig3.gap(df, gap_min=20, mode="cont", spec=trl)),
        ("gap-fade trail4",sig3.gap(df, gap_min=20, mode="fade", spec=trl)),
        ("volx k0.4 tp4",  sig3.vol_expand(df, k=0.4, spec=tp4)),
        ("volx k0.6 tp4",  sig3.vol_expand(df, k=0.6, spec=tp4)),
        ("volx k0.4 trail4",sig3.vol_expand(df, k=0.4, spec=trl)),
        ("power thr40 tp4",sig3.power_hour(df, thr_pts=40, spec=tp4)),
        ("power thr40 trl4",sig3.power_hour(df, thr_pts=40, spec=trl)),
        ("nr_break tp4",   sig3.nr_break(df, spec=tp4)),
        ("nr_break trail4",sig3.nr_break(df, spec=trl)),
    ]:
        r=score(nm,o,df,ad)
        if r: res.append(r)
    res.sort(key=lambda x:-x[2])
    print("-"*120); print("TOP by 4-week pass:", [f"{n} {p*100:.0f}%" for n,_,p in res[:4]])

if __name__=="__main__":
    main()
