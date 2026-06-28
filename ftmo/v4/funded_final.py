"""
ftmo/v4/funded_final.py — iteration 7: lock the funded winner around the 6R peak.
Per-setup TP, finer risk, cost sensitivity, withdrawal buffer, in/out-of-sample.
Reuses the bug-checked funded engine (funded_opt).

Run: python3 funded_final.py
"""
import numpy as np
import data, strategies as S, engine
import funded_opt as FO
from funded_search import best_risk

O, EU = 16*60, 11*60

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique())); mid=ad[len(ad)//2]
    def cfg(orb_tp=6.0, vp_tp=6.0, vp_trail=3.0):
        return (S.orb(df,open_min=O,or_min=30,stop_pts=60,tp_R=orb_tp,be_R=1.0,vol_filter=True)
               +S.orb(df,open_min=EU,or_min=30,stop_pts=60,tp_R=orb_tp,be_R=1.0,vol_filter=True)
               +S.vwap_pullback(df,stop_pts=40,tp_R=vp_tp,trail_R=vp_trail))
    def days(orders,cost=FO.COST): return FO.build_days(engine.simulate(df,orders,cost_pts=cost),ad)

    print("="*96); print("FTMO funded iter7 — lock around the 6R peak"); print("="*96)

    # 1) per-setup TP (ORB fixed 6R; vary pullback TP)
    print("per-setup TP (ORB 6R, vary pullback):")
    best=None
    for vp_tp in [4,6,8]:
        o=cfg(6.0,vp_tp,3.0); r,s=best_risk(days(o))
        print(f"   ORB6 + VWpull{vp_tp}R: ${r:.0f} -> net ${s['net_mo']:.0f}/mo (avg ${s['avg']:.0f}, med ${s['med']:.0f})")
        if best is None or s['net_mo']>best[2]['net_mo']: best=(vp_tp,r,s,o)
    vp_tp,br,bs,bo=best
    print(f"  -> best pullback TP = {vp_tp}R at ${br:.0f}/trade, net ${bs['net_mo']:.0f}/mo")

    # 2) finer risk on the winner
    print("\nfiner risk sweep on the winner:")
    for r in [75,90,100,110,125]:
        s=FO.score(FO.funded_mc(days(bo),r,N=50000,buffer=0.0,cadence=14,gate=14))
        print(f"   ${r}: net ${s['net_mo']:.0f}/mo  avg ${s['avg']:.0f}  med ${s['med']:.0f}  blow {s['blow']*100:.0f}%")

    # 3) withdrawal buffer on the winner
    print("\nwithdrawal buffer (cadence 14d):")
    for buf in [0,250,500,1000]:
        s=FO.score(FO.funded_mc(days(bo),br,N=50000,buffer=float(buf),cadence=14,gate=14))
        print(f"   BE+${buf:5d}: net ${s['net_mo']:.0f}/mo  avg ${s['avg']:.0f}  med ${s['med']:.0f}  blow {s['blow']*100:.0f}%  {s['npay']:.1f}pay")

    # 4) cost sensitivity + in/out-of-sample on the winner
    print("\ncost sensitivity:")
    for c in [1.0,2.0,3.0]:
        r,s=best_risk(days(bo,cost=c))
        print(f"   COST {c:.1f}pt: ${r:.0f} -> net ${s['net_mo']:.0f}/mo")
    tr=engine.simulate(df,bo,cost_pts=FO.COST)
    d1=FO.build_days(tr[tr["day"]<mid],ad[ad<mid]); d2=FO.build_days(tr[tr["day"]>=mid],ad[ad>=mid])
    s1=FO.score(FO.funded_mc(d1,br,N=50000,buffer=0.0,cadence=14,gate=14))
    s2=FO.score(FO.funded_mc(d2,br,N=50000,buffer=0.0,cadence=14,gate=14))
    es=engine.edge_stats(tr)
    print(f"\nin/out-of-sample: H1 ${s1['net_mo']:.0f}/mo · H2 ${s2['net_mo']:.0f}/mo   WR {es['wr']*100:.0f}%  expR {es['expR']:+.3f}")
    print("="*96)
    print(f"FINAL: US ORB(16:00) + EU ORB(11:00) [30m,60pt,6R,BE@1R,vol] + VWpull[40pt,{vp_tp}R,trail3R]")
    print(f"  risk ${br:.0f}/trade (~{br/15000*100:.2f}%), withdraw every 14d to breakeven")
    print(f"  -> NET ${bs['net_mo']:.0f}/mo · avg banked ${bs['avg']:.0f} · median ${bs['med']:.0f} · "
          f"first payout ~{bs['tfirst']:.0f}d · {bs['npay']:.1f} payouts · life {bs['life_mo']:.1f}mo")

if __name__=="__main__":
    main()
