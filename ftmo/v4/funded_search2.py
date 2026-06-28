"""
ftmo/v4/funded_search2.py — iteration 5: push beyond the converged ORB+VWpull leader.
New angles: trend-RUNNERS (trail, no hard TP -> capture NQ fat tails = bigger withdrawals),
the 17:00 server volume-PEAK session, and other library strategies (IB break, open-drive,
PDH/PDL). Ranked by net banked $/month on the bug-checked funded engine. Reuses funded_opt.

Run: python3 funded_search2.py
"""
import numpy as np
import data, strategies as S, engine
import funded_opt as FO
from funded_search import days_of, best_risk

O, EU, H17 = 16*60, 11*60, 17*60

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    orb=lambda om,tp=3.0,be=1.0,tr=0.0,st=60: S.orb(df,open_min=om,or_min=30,stop_pts=st,tp_R=tp,be_R=be,trail_R=tr,vol_filter=True)
    vp =lambda tp=4.0,tr=3.0,st=40: S.vwap_pullback(df,stop_pts=st,tp_R=tp,trail_R=tr)
    W = orb(O)+orb(EU)+vp()                                   # the converged winner

    bat={
      "WINNER US+EU ORB+VWpull":   W,
      # trend-runners (let winners ride; capture fat tails)
      "ORB trail4(noTP)+VWpull":   orb(O,tp=0.0,tr=4.0)+orb(EU,tp=0.0,tr=4.0)+vp(),
      "ORB tp6 be1 + VWpull":      orb(O,tp=6.0)+orb(EU,tp=6.0)+vp(),
      "ORB tp3 + VWpull trail4noTP":orb(O)+orb(EU)+vp(tp=0.0,tr=4.0),
      "ORB tp8 + VWpull tp8":      orb(O,tp=8.0)+orb(EU,tp=8.0)+vp(tp=8.0),
      # 17:00 volume-peak session
      "17h+EU ORB + VWpull":       orb(H17)+orb(EU)+vp(),
      "US+17h ORB + VWpull":       orb(O)+orb(H17)+vp(),
      # other library strategies
      "IBbreak60 US+EU + VWpull":  S.ib_break(df,ib_min=60,stop_pts=60,trail_R=3.0,open_min=O)+S.ib_break(df,ib_min=60,stop_pts=60,trail_R=3.0,open_min=EU)+vp(),
      "WINNER + open_drive":       W+S.open_drive(df,stop_pts=50,trail_R=3.0,open_min=O),
      "WINNER + PDHL":             W+S.pdh_pdl(df,stop_pts=60,trail_R=3.0,open_min=O),
    }
    print("="*100)
    print("FTMO funded — iteration 5: runners / 17h session / other strategies vs the winner")
    print(f"COST={FO.COST}pt, cadence 14d, withdraw-to-BE, ACQ=${FO.ACQ:.0f}")
    print("="*100)
    print(f"  {'strategy':30}{'risk$':>6} | {'net$/mo':>8}{'avgBank':>8}{'medBank':>8}{'blow%':>6}{'life(mo)':>8}{'WR%':>5}{'expR':>7}")
    rows=[]
    for name,orders in bat.items():
        es=engine.edge_stats(engine.simulate(df,orders,cost_pts=FO.COST))
        r,s=best_risk(days_of(df,ad,orders))
        rows.append((name,r,s,es))
        print(f"  {name:30}{r:6.0f} | {s['net_mo']:8.0f}{s['avg']:8.0f}{s['med']:8.0f}{s['blow']*100:5.0f}%"
              f"{s['life_mo']:8.1f}{es['wr']*100:5.0f}{es['expR']:+7.3f}")
    rows.sort(key=lambda x:x[2]["net_mo"],reverse=True)
    print("-"*100)
    bn,br,bs,be=rows[0]
    base=next(r for r in rows if r[0].startswith("WINNER US+EU"))
    print(f"BEST: {bn}  ${br:.0f}/trade -> NET ${bs['net_mo']:.0f}/mo  (prior winner ${base[2]['net_mo']:.0f}/mo)")
    if bs['net_mo'] > base[2]['net_mo']*1.03:
        print("  -> NEW LEADER (>3% gain). Robustness check:")
        mid=ad[len(ad)//2]; tr=engine.simulate(df,bat[bn],cost_pts=FO.COST)
        d1=FO.build_days(tr[tr["day"]<mid],ad[ad<mid]); d2=FO.build_days(tr[tr["day"]>=mid],ad[ad>=mid])
        s1=FO.score(FO.funded_mc(d1,br,N=40000,buffer=0.0,cadence=14,gate=14))
        s2=FO.score(FO.funded_mc(d2,br,N=40000,buffer=0.0,cadence=14,gate=14))
        print(f"     in/out-of-sample: H1=${s1['net_mo']:.0f} H2=${s2['net_mo']:.0f}")
    else:
        print("  -> no material improvement over the converged winner.")

if __name__=="__main__":
    main()
