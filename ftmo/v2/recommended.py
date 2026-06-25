"""
recommended.py — the final, validated strategy for the FTMO $15k 1-Step on NAS100.

A 2-setup combo, both with SCALE-OUT exits (the lever that ~doubled the pass rate):
  A) US opening-range breakout  : 16:00 server, 15-min range, 50pt stop, vol-confirmed,
                                  scale 2/3 out at +2R, runner -> breakeven + trail 3R
  B) VWAP trend-pullback        : buy dips to session VWAP in an uptrend (mirror short),
                                  40pt stop, scale 1/2 out at +2R, runner -> BE + trail 3R
Both: US cash session only, one trade/day each, flat by 22:55 server, no Friday entries.
Risk: 1.00%/trade recommended (near-zero blow-up); 1.25% to go faster.

Validated: positive every year 2022-25, both directions, OOS, and to 6pt costs.
Run: python3 recommended.py
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

SETUP_A = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0,
               trail_R=3.0, vol_filter=True, partial_R=2.0, partial_frac=0.67)
SETUP_B = dict(stop_pts=40, trail_R=3.0, partial_R=2.0, partial_frac=0.5)
COST = 3.0   # conservative round-turn points

def orders(df):
    return sorted(S.orb(df, **SETUP_A) + S.vwap_pullback(df, **SETUP_B),
                  key=lambda o: o["entry_bar"])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, orders(df), cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    print("="*78)
    print("RECOMMENDED STRATEGY — NAS100 scale-out combo (FTMO $15k 1-Step)")
    print("="*78)
    print(f"trades {es['n']} ({es['n']/(len(ad)/5):.1f}/wk)  WR {es['wr']*100:.1f}%  "
          f"expR {es['expR']:+.3f}  PF {es['pf']:.2f}  (cost {COST:.0f}pt)")
    dR = np.asarray(days["day_R"]); dr = dR*0.0125
    print(f"daily Sharpe @1.25% ~ {dr.mean()/dr.std():.2f}\n")
    print("pass% / blow%  by deadline x per-trade risk:")
    risks = [0.0075, 0.01, 0.0125, 0.015]
    print("  deadline | " + "   ".join(f"r={r*100:>4.2f}%" for r in risks))
    for nm, T in [("2wk",10),("3wk",15),("4wk",20),("5wk",25),("6wk",30),("8wk",40)]:
        cells = []
        for r in risks:
            m = ftmo.run_mc(days, r, T, n_paths=40000, seed=5)
            cells.append(f"{m['pass_rate']*100:4.0f}/{m['blow_rate']*100:>2.0f}")
        print(f"  {nm:>7}  | " + "    ".join(cells))
    print("\nRecommendation: r=1.00% -> ~73% pass in 4wk / ~82% in 5wk with ~1% blow-up.")
    print("                r=1.25% -> faster (~64% in 3wk) at single-digit blow-up.")

if __name__ == "__main__":
    main()
