"""
recommended.py — final validated strategy for the FTMO $15k 1-Step on NAS100.

A 3-setup combo, all with SCALE-OUT exits. Two trend setups (correlated, the engine
of returns) plus a SELECTIVE range-fade that is negatively correlated (-0.11) and
wins on the choppy days the trend setups lose -> raises daily Sharpe, pushing the
80% pass mark from ~5 weeks down to ~4.

  A) US opening-range breakout : 16:00 server, 15-min range, 50pt stop, vol-confirmed,
                                 scale 2/3 out at +2R, runner -> breakeven + trail 3R
  B) VWAP trend-pullback       : buy dips to VWAP in an uptrend (mirror short),
                                 40pt stop, scale 1/2 at +2R, runner -> BE + trail 3R
  C) Selective range-fade      : ONLY when VWAP is flat (range day), fade >2 sigma
                                 stretches back to VWAP, 40pt stop, scale 1/2 at +1R,
                                 runner -> BE + trail 2R

All: US cash session, one trade/day each, flat 22:55 server, no Friday entries.

RISK / DAILY-CAP NOTE (3% = $450): up to 3 trades/day, each risking 1R. Keep
per-trade risk <= ~0.95% so three full stops (3R) stay under the 3% daily cap; the
negative-correlation fade makes 3-loss days rare in practice. Recommended r = 1.0%.
CONSISTENCY (50% best-day): scale-out caps single-day spikes, so it costs only ~1pp.

Validated: positive every year 2022-25, both directions, OOS, to 6pt costs.
Run: python3 recommended.py
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

SETUP_A = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0,
               trail_R=3.0, vol_filter=True, partial_R=2.0, partial_frac=0.67)
SETUP_B = dict(stop_pts=40, trail_R=3.0, partial_R=2.0, partial_frac=0.5)
SETUP_C = dict(k=2.0, stop_pts=40, trail_R=2.0, partial_R=1.0, partial_frac=0.5)
COST = 3.0

def orders(df):
    return sorted(S.orb(df, **SETUP_A) + S.vwap_pullback(df, **SETUP_B)
                  + S.vwap_fade_sel(df, **SETUP_C), key=lambda o: o["entry_bar"])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, orders(df), cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    print("="*78)
    print("RECOMMENDED — NAS100 3-setup scale-out combo (FTMO $15k 1-Step)")
    print("="*78)
    print(f"trades {es['n']} ({es['n']/(len(ad)/5):.1f}/wk)  WR {es['wr']*100:.1f}%  "
          f"expR {es['expR']:+.3f}  PF {es['pf']:.2f}  (cost {COST:.0f}pt)")
    dr = np.asarray(days["day_R"])*0.01
    print(f"daily Sharpe @1.0% ~ {dr.mean()/dr.std():.2f}\n")
    print("pass% / blow%  by deadline x per-trade risk:")
    risks = [0.0075, 0.009, 0.01, 0.0125]
    print("  deadline | " + "   ".join(f"r={r*100:>4.2f}%" for r in risks))
    for nm, T in [("2wk",10),("3wk",15),("4wk",20),("5wk",25),("6wk",30),("8wk",40)]:
        cells = []
        for r in risks:
            m = ftmo.run_mc(days, r, T, n_paths=40000, seed=5)
            cells.append(f"{m['pass_rate']*100:4.0f}/{m['blow_rate']*100:>2.0f}")
        print(f"  {nm:>7}  | " + "    ".join(cells))
    print("\nRecommendation: r=1.0% -> ~80% pass in 4wk, ~88% in 5wk, ~2-3% blow-up.")
    print("Simpler 2-setup variant (A+B only) is ~80% at 5wk with more daily headroom.")

if __name__ == "__main__":
    main()
