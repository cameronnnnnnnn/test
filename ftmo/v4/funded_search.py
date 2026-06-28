"""
ftmo/v4/funded_search.py — iteration 3: broaden the FTMO funded strategy search (more
trades/day, higher-WR/lower-R, extra sessions, fades) and robustness-check the winner
in/out-of-sample and across costs. Reuses the bug-checked funded_opt engine.

Run: python3 funded_search.py
"""
import numpy as np, pandas as pd
import data, strategies as S, engine
import funded_opt as FO

O, EU, EU2 = 16*60, 11*60, 10*60          # US open, EU open, EU early (server time)

def days_of(df, ad, orders, cost=FO.COST):
    return FO.build_days(engine.simulate(df, orders, cost_pts=cost), ad)

def best_risk(days, risks=(60,75,90,100,110,125,150,175,200), cad=14, buf=0.0):
    best=None
    for r in risks:
        s=FO.score(FO.funded_mc(days, r, N=40000, buffer=buf, cadence=cad, gate=cad))
        if best is None or s["net_mo"]>best[1]["net_mo"]: best=(r,s)
    return best

def main():
    df=S.prep(data.load()); ad=np.array(sorted(df["date"].unique()))
    orb=lambda om,orm=30,st=60,tp=3.0,be=1.0: S.orb(df,open_min=om,or_min=orm,stop_pts=st,tp_R=tp,be_R=be,vol_filter=True)
    vp =lambda st=40,tp=4.0: S.vwap_pullback(df,stop_pts=st,tp_R=tp)
    fade=lambda st=40,tp=1.0: S.vwap_fade(df,k=2.0,stop_pts=st,tp_R=tp)

    bat={
      "US+EU ORB30 (leader)":   orb(O)+orb(EU),
      "US+EU+10h ORB30 (3sess)":orb(O)+orb(EU)+orb(EU2),
      "US+EU ORB30 + VWpull":   orb(O)+orb(EU)+vp(),
      "US+EU+10h ORB + VWpull": orb(O)+orb(EU)+orb(EU2)+vp(),
      "US+EU ORB30 tp2 (hiWR)": orb(O,tp=2.0)+orb(EU,tp=2.0),
      "US+EU ORB30 tp4":        orb(O,tp=4.0)+orb(EU,tp=4.0),
      "combo ORB15+VWpull4R":   S.orb(df,open_min=O,or_min=15,stop_pts=50,tp_R=4.0,vol_filter=True)+vp(),
      "US+EU ORB30 + fade":     orb(O)+orb(EU)+fade(),
      "EU ORB30 only":          orb(EU),
    }
    print("="*98)
    print("FTMO funded — BROAD strategy search (cadence 14d, withdraw-to-BE; best risk shown)")
    print(f"static $13.5k floor, 3% daily, 90/10, 50% rule, COST={FO.COST}pt, ACQ=${FO.ACQ:.0f}")
    print("="*98)
    print(f"  {'strategy':26}{'risk$':>6} | {'net$/mo':>8}{'avgBank':>8}{'medBank':>8}{'blow%':>6}{'life(mo)':>8}{'#pay':>5}{'WR%':>5}")
    rows=[]
    for name,orders in bat.items():
        es=engine.edge_stats(engine.simulate(df,orders,cost_pts=FO.COST))
        days=days_of(df,ad,orders)
        r,s=best_risk(days)
        rows.append((name,orders,r,s,es))
        print(f"  {name:26}{r:6.0f} | {s['net_mo']:8.0f}{s['avg']:8.0f}{s['med']:8.0f}{s['blow']*100:5.0f}%"
              f"{s['life_mo']:8.1f}{s['npay']:5.1f}{es['wr']*100:5.0f}")
    rows.sort(key=lambda x:x[3]["net_mo"],reverse=True)
    print("-"*98)
    wname,worders,wr,ws,wes=rows[0]
    print(f"LEADER: {wname}  risk ${wr:.0f}/trade, 14d cadence, withdraw to BE -> NET ${ws['net_mo']:.0f}/mo")
    wdays=days_of(df,ad,worders)
    print("  withdrawal-buffer check on leader (cadence 14d):")
    for buf in [0.0,250.0,500.0,1000.0]:
        s=FO.score(FO.funded_mc(wdays,wr,N=40000,buffer=buf,cadence=14,gate=14))
        print(f"    leave BE+${buf:5.0f}: net ${s['net_mo']:.0f}/mo (avg ${s['avg']:.0f}, med ${s['med']:.0f}, blow {s['blow']*100:.0f}%, {s['npay']:.1f} pay)")

    # ---- robustness on the winner: in/out-of-sample + cost sensitivity ----
    print("\n"+"="*98); print(f"ROBUSTNESS — {wname} @ ${wr:.0f}, 14d"); print("="*98)
    mid=ad[len(ad)//2]
    tr=engine.simulate(df,worders,cost_pts=FO.COST)
    d1=FO.build_days(tr[tr["day"]<mid], ad[ad<mid]); d2=FO.build_days(tr[tr["day"]>=mid], ad[ad>=mid])
    s1=FO.score(FO.funded_mc(d1,wr,N=40000,buffer=0.0,cadence=14,gate=14))
    s2=FO.score(FO.funded_mc(d2,wr,N=40000,buffer=0.0,cadence=14,gate=14))
    print(f"  in/out-of-sample net $/mo:  H1={s1['net_mo']:.0f}  H2={s2['net_mo']:.0f}  "
          f"(full={ws['net_mo']:.0f})  -> {'ROBUST' if min(s1['net_mo'],s2['net_mo'])>0.5*ws['net_mo'] else 'FRAGILE'}")
    print("  cost sensitivity (full sample):")
    for c in [1.0,2.0,3.0]:
        dc=days_of(df,ad,worders,cost=c); rc,sc=best_risk(dc)
        print(f"    COST={c:.1f}pt -> best risk ${rc:.0f}, net ${sc['net_mo']:.0f}/mo  (avg ${sc['avg']:.0f}, blow {sc['blow']*100:.0f}%)")

if __name__=="__main__":
    main()
