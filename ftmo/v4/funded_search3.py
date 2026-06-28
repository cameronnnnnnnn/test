"""
ftmo/v4/funded_search3.py — iteration 6: find the robust 'let winners run' level.
Iter 5 showed bigger take-profits (8R) bank more (fat-tail capture). Sweep the TP/trail
frontier for the US+EU ORB + VWpull combo, with PER-CONFIG in/out-of-sample robustness so
we adopt a robust peak, not a bull-overfit one. Reuses the bug-checked funded engine.

Run: python3 funded_search3.py
"""
import numpy as np
import data, strategies as S, engine
import funded_opt as FO
from funded_search import best_risk

O, EU = 16*60, 11*60
RISKS=(75,100,125,150)

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique())); mid=ad[len(ad)//2]
    def combo(tp, trail_vp=3.0, trail_orb=0.0):
        return (S.orb(df,open_min=O,or_min=30,stop_pts=60,tp_R=tp,be_R=1.0,trail_R=trail_orb,vol_filter=True)
               +S.orb(df,open_min=EU,or_min=30,stop_pts=60,tp_R=tp,be_R=1.0,trail_R=trail_orb,vol_filter=True)
               +S.vwap_pullback(df,stop_pts=40,tp_R=tp,trail_R=trail_vp))
    def evalc(orders):
        tr=engine.simulate(df,orders,cost_pts=FO.COST)
        days=FO.build_days(tr,ad); r,s=best_risk(days,risks=RISKS)
        d1=FO.build_days(tr[tr["day"]<mid],ad[ad<mid]); d2=FO.build_days(tr[tr["day"]>=mid],ad[ad>=mid])
        s1=FO.score(FO.funded_mc(d1,r,N=40000,buffer=0.0,cadence=14,gate=14))
        s2=FO.score(FO.funded_mc(d2,r,N=40000,buffer=0.0,cadence=14,gate=14))
        es=engine.edge_stats(tr)
        return r,s,s1,s2,es

    print("="*104)
    print("FTMO funded iter6 — 'let winners run' frontier (US+EU ORB + VWpull), robust peak")
    print(f"COST={FO.COST}pt, 14d cadence, withdraw-to-BE")
    print("="*104)
    print(f"  {'config':26}{'risk$':>6} | {'net$/mo':>8}{'H1':>6}{'H2':>6} {'avgBank':>8}{'medBank':>8}{'blow%':>6}{'WR%':>5}{'expR':>7}")
    rows=[]
    # A) hard-TP family
    for tp in [4,6,8,10,12,15,20]:
        r,s,s1,s2,es=evalc(combo(tp))
        rows.append((f"hardTP {tp}R",r,s,s1,s2,es))
    # B) pure-trail family (tp=0, ride the trail)
    for tr_ in [4,6,8,10]:
        r,s,s1,s2,es=evalc(combo(0.0,trail_vp=tr_,trail_orb=tr_))
        rows.append((f"trail {tr_}R (noTP)",r,s,s1,s2,es))
    for name,r,s,s1,s2,es in rows:
        print(f"  {name:26}{r:6.0f} | {s['net_mo']:8.0f}{s1['net_mo']:6.0f}{s2['net_mo']:6.0f} "
              f"{s['avg']:8.0f}{s['med']:8.0f}{s['blow']*100:5.0f}%{es['wr']*100:5.0f}{es['expR']:+7.3f}")
    # robust ranking: min(H1,H2) must be healthy; rank by full net then require both halves > prior winner halves
    print("-"*104)
    robust=[x for x in rows if min(x[3]['net_mo'],x[4]['net_mo'])>520]   # both halves beat the old winner's weaker half
    robust.sort(key=lambda x:x[2]['net_mo'],reverse=True)
    if robust:
        bn,br,bs,bs1,bs2,bes=robust[0]
        print(f"ROBUST BEST: {bn}  ${br:.0f}/trade -> NET ${bs['net_mo']:.0f}/mo  (H1 ${bs1['net_mo']:.0f} / H2 ${bs2['net_mo']:.0f})")
        print(f"  avg banked ${bs['avg']:.0f}  median ${bs['med']:.0f}  blow {bs['blow']*100:.0f}%  life {bs['life_mo']:.1f}mo")
    else:
        print("no config passes the robustness bar.")

if __name__=="__main__":
    main()
