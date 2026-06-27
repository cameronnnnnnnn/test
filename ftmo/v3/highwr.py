"""
v3/highwr.py — high-WR / low-RR geometry (wide stop, tight take-profit) under the
exact FTMO rules. Premise (prop-firm convex payoff): pass rate is driven by LOW P&L
variance, not high expR. Sweep tp_R (TP as a fraction of the 1R stop) on momentum
(ORB) and mean-reversion (VWAP-fade) entries; report WR, expR, 4-week pass, and
median days-to-pass. Corrected engine. Prioritise WR>=50% and median pass <20 days.
"""
import numpy as np, pandas as pd, strategies as S, engine, ftmo, data
from run import build_days
COST = 3.0
RISKS = [0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025]

def score(name, orders, df, ad):
    tr = engine.simulate(df, orders, cost_pts=COST)
    if len(tr) < 100:
        print(f"  {name:24s} few({len(tr)})"); return None
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    res = [(r, ftmo.run_mc(days, r, 20, n_paths=30000, seed=5)) for r in RISKS]
    r4, m4 = max(res, key=lambda x: x[1]["pass_rate"])
    m3 = ftmo.run_mc(days, r4, 15, n_paths=30000, seed=5)
    print(f"  {name:24s} {es['n']/(len(ad)/5):4.1f}/wk WR={es['wr']*100:4.1f}% expR={es['expR']:+.3f} | "
          f"4wk pass={m4['pass_rate']*100:4.1f}% blow={m4['blow_rate']*100:4.1f}% r={r4*100:.2f}% "
          f"medDays={m4['med_days_to_pass']} | 3wk={m3['pass_rate']*100:4.1f}%")
    return (name, es['wr'], m4['pass_rate'], m4['med_days_to_pass'], m4['blow_rate'])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    print("HIGH-WR / LOW-RR geometry under FTMO (corrected engine). Prioritise WR>=50%, medDays<20.")
    print("--- momentum ORB entry, tight TP (wide stop = 1R) ---")
    res = []
    for tp in [0.25, 0.5, 0.75, 1.0]:
        for stop in [50, 80]:
            r = score(f"ORB s{stop} tp{tp}R",
                      S.orb(df, open_min=16*60, or_min=15, stop_pts=stop, vol_filter=True,
                            tp_R=tp, be_R=0.0, trail_R=0.0), df, ad)
            if r: res.append(r)
    print("--- mean-reversion (VWAP-fade) entry, tight TP — naturally high WR ---")
    for tp in [0.25, 0.5, 0.75]:
        for k in [1.0, 1.5, 2.0]:
            orders = S.vwap_fade(df, k=k, stop_pts=50, tp_R=tp)
            r = score(f"fade k{k} tp{tp}R", orders, df, ad)
            if r: res.append(r)
    res.sort(key=lambda x: -x[2])
    print("-"*70)
    print("TOP by 4-week pass (WR>=50% only):")
    for n,wr,p,md,b in [x for x in res if x[1]>=0.5][:6]:
        print(f"  {n:24s} WR={wr*100:.0f}% 4wkPass={p*100:.0f}% medDays={md} blow={b*100:.0f}%")

if __name__ == "__main__":
    main()
