"""
exitsearch.py — exhaustive exit-strategy search on the core edge (US ORB, vol-
confirmed, 50pt stop) with the CORRECTED engine. Tests pure trail, trail+breakeven,
fixed-RR take-profits, scale-out (partial+runner), and scale-out+TP — ranked by the
FTMO 3-week pass rate, then the winner is validated out-of-sample.

Honest framing: trail-only maximizes expR (the edge is the fat tail); BE/scale-out/
fixed-TP trade drift for lower variance + higher WR. Which wins the PASS RATE (drift
vs variance vs the 50% consistency rule) is what we measure here.
"""
import numpy as np, pandas as pd, strategies as S, engine, ftmo, data
from run import build_days

COST = 3.0
RISKS = [0.0075, 0.01, 0.0125, 0.015, 0.02]
BASE = dict(open_min=16*60, or_min=15, stop_pts=50, vol_filter=True)

def EX(tp=0.0, be=0.0, trail=0.0, pr=0.0, pf=0.5):
    # full exit spec every time so orb's defaults (tp_R=3,be_R=1) never leak in
    return dict(tp_R=tp, be_R=be, trail_R=trail, partial_R=pr, partial_frac=pf)

def best(days, T):
    return max((ftmo.run_mc(days, r, T, n_paths=25000, seed=5) for r in RISKS),
               key=lambda m: m["pass_rate"])

def score(df, ad, exit_kw):
    orders = S.orb(df, **BASE, **exit_kw)
    tr = engine.simulate(df, orders, cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    m3, m4, m8 = best(days, 15), best(days, 20), best(days, 40)
    return es, (m3, m4, m8), tr

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    grid = []
    # pure trail
    for tr in [2, 2.5, 3, 4]:
        grid.append((f"trail{tr}", EX(trail=tr)))
    # trail + breakeven
    for be in [0.5, 1.0, 1.5]:
        for tr in [3, 4]:
            grid.append((f"be{be}+trail{tr}", EX(be=be, trail=tr)))
    # fixed-RR take-profit (optionally with BE)
    for tp in [1.5, 2, 3, 4]:
        grid.append((f"tp{tp}", EX(tp=tp)))
    for tp in [2, 3, 4]:
        grid.append((f"be1+tp{tp}", EX(be=1.0, tp=tp)))
    # scale-out: partial + runner trail
    for pr in [1.0, 1.5, 2.0]:
        for pf in [0.3, 0.5, 0.7]:
            grid.append((f"p{pr}/{pf}+trl3", EX(pr=pr, pf=pf, trail=3.0)))
    # scale-out + fixed-RR runner
    for pr in [1.5, 2.0]:
        grid.append((f"p{pr}/.5+tp4", EX(pr=pr, pf=0.5, tp=4.0)))

    rows = []
    for name, kw in grid:
        es, (m3, m4, m8), _ = score(df, ad, kw)
        rows.append((name, es, m3, m4, m8))
    rows.sort(key=lambda r: -r[2]["pass_rate"])

    print("="*108)
    print("EXIT-STRATEGY SEARCH on US ORB (corrected engine, cost 3pt). Ranked by 3-week pass.")
    print(f"{'exit':16s} {'WR':>5} {'expR':>7} {'PF':>5} | {'3wk p/b':>11} {'4wk p/b':>11} {'8wk p/b':>11}")
    print("-"*108)
    for name, es, m3, m4, m8 in rows:
        print(f"{name:16s} {es['wr']*100:4.1f}% {es['expR']:+6.3f} {es['pf']:5.2f} | "
              f"{m3['pass_rate']*100:4.0f}/{m3['blow_rate']*100:<5.0f} "
              f"{m4['pass_rate']*100:4.0f}/{m4['blow_rate']*100:<5.0f} "
              f"{m8['pass_rate']*100:4.0f}/{m8['blow_rate']*100:<5.0f}")

    # validate the top config OOS
    top = rows[0]; name = top[0]
    kw = dict(grid[[g[0] for g in grid].index(name)][1])
    print("\n" + "="*60)
    print(f"OOS VALIDATION of winner: {name}")
    es, _, tr = score(df, ad, kw)
    tr["yr"] = pd.to_datetime(tr["entry_dt"]).dt.year
    for y, g in tr.groupby("yr"):
        print(f"  {y}: expR={g['R'].mean():+.3f}")
    cut = ad[int(len(ad)*0.67)]
    print(f"  in-sample expR={tr[tr.entry_dt<cut]['R'].mean():+.3f}  "
          f"OOS expR={tr[tr.entry_dt>=cut]['R'].mean():+.3f}")
    oos = ad[ad >= cut]; do = build_days(tr[tr.entry_dt>=cut], oos)
    for nm, T in [("3wk",15),("4wk",20),("8wk",40)]:
        m = best(do, T)
        print(f"  OOS {nm}: pass={m['pass_rate']*100:.0f}% blow={m['blow_rate']*100:.0f}%")

if __name__ == "__main__":
    main()
