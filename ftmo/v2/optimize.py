"""
optimize.py — tune the scale-out ORB (the breakthrough config) and test the
combo with VWAP-pullback. Conservative 3pt round-turn cost throughout.
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

COST = 3.0
RISKS = [0.0075, 0.01, 0.0125, 0.015, 0.02]

def score(orders, df, ad, deads=(15,)):
    tr = engine.simulate(df, orders, cost_pts=COST)
    if len(tr) < 50:
        return None
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    out = dict(n=es["n"], wr=es["wr"], expR=es["expR"], maxR=es["maxR"])
    for T in deads:
        best = max((ftmo.run_mc(days, r, T, n_paths=20000, seed=5) for r in RISKS),
                   key=lambda m: m["pass_rate"])
        out[T] = (best["pass_rate"], best["blow_rate"])
    return out

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    print("Tuning scale-out ORB (cost 3pt). Ranking by 3-week pass.\n" + "="*100)
    grid = []
    for stop in [40, 50, 60]:
        for pR in [1.5, 2.0, 2.5]:
            for pf in [0.33, 0.5, 0.67]:
                for tr in [2.0, 3.0]:
                    p = dict(open_min=16*60, or_min=15, stop_pts=stop, tp_R=0.0, be_R=0.0,
                             trail_R=tr, vol_filter=True, partial_R=pR, partial_frac=pf)
                    s = score(S.orb(df, **p), df, ad)
                    if s:
                        grid.append((f"s{stop} p{pR} f{pf:.2f} tr{tr}", s, p))
    grid.sort(key=lambda x: -x[1][15][0])
    print("top 12 by 3-week pass:")
    for name, s, p in grid[:12]:
        print(f"  {name:24s} WR={s['wr']*100:4.1f}% expR={s['expR']:+.3f} maxR={s['maxR']:4.1f} "
              f"| 3wk pass={s[15][0]*100:4.1f}% blow={s[15][1]*100:4.1f}%")

    print("\nfull frontier for the winner + combo with VWAP-pullback (scale-out):")
    bestp = grid[0][2]
    winner = S.orb(df, **bestp)
    vw = S.vwap_pullback(df, stop_pts=40, trail_R=3.0, partial_R=2.0, partial_frac=0.5)
    combo = sorted(winner + vw, key=lambda o: o["entry_bar"])
    for label, orders in [("WINNER orb-scaleout", winner), ("COMBO orb+vwpull scaleout", combo)]:
        tr = engine.simulate(df, orders, cost_pts=COST); days = build_days(tr, ad)
        es = engine.edge_stats(tr)
        print(f"\n  {label}: n={es['n']} ({es['n']/(len(ad)/5):.1f}/wk) WR={es['wr']*100:.1f}% expR={es['expR']:+.3f}")
        for nm, T in [("2wk",10),("3wk",15),("4wk",20),("6wk",30),("8wk",40)]:
            res = [(r, ftmo.run_mc(days, r, T, n_paths=30000, seed=5)) for r in RISKS]
            r, m = max(res, key=lambda x: x[1]["pass_rate"])
            print(f"     {nm:>4} best r={r*100:4.2f}%: pass={m['pass_rate']*100:4.1f}% "
                  f"blow={m['blow_rate']*100:4.1f}%  (med days-to-pass {m['med_days_to_pass']})")

if __name__ == "__main__":
    main()
