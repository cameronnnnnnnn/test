"""
recommended.py — corrected, validated strategy for the FTMO $15k 1-Step on NAS100.

NOTE: an earlier "scale-out" version was withdrawn — a backtest bug had booked
losing trades at a fraction of -1R, which inflated scale-out results. With losses
correctly at -1R, scale-out CAPS the fat tail that is the actual edge and turns the
combo negative. The real edge is TRAIL-ONLY breakout/continuation.

Strategy (trail-only, no scale-out):
  A) US Opening-Range Breakout : 16:00 server, 15m range, 50pt stop, volume-confirmed,
                                 trail 3R behind the extreme, EOD-flat.
  B) VWAP trend-pullback        : buy dips to session VWAP in an uptrend (mirror short),
                                 40pt stop, trail 3R.
One trade/day per setup, US cash session, flat 22:55, Fridays ON (they help).

This is a THIN, real edge: expR ~+0.06-0.09R, WR ~29%. It does NOT pass 80% in 3
weeks (the fat-tailed, low-WR payoff can't). Honest frontier below.
Run: python3 recommended.py
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

SETUP_A = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0,
               trail_R=3.0, vol_filter=True)            # trail-only, no partial
SETUP_B = dict(stop_pts=40, trail_R=3.0)                # trail-only, no partial
COST = 3.0

def orders(df):
    return sorted(S.orb(df, **SETUP_A) + S.vwap_pullback(df, **SETUP_B),
                  key=lambda o: o["entry_bar"])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, orders(df), cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    print("="*70)
    print("RECOMMENDED (corrected) — NAS100 trail-only ORB + VWAP-pullback")
    print("="*70)
    print(f"trades {es['n']} ({es['n']/(len(ad)/5):.1f}/wk)  WR {es['wr']*100:.1f}%  "
          f"expR {es['expR']:+.3f}  PF {es['pf']:.2f}  (cost {COST:.0f}pt)")
    print("\npass% / blow%  by deadline x per-trade risk:")
    risks = [0.0075, 0.01, 0.0125, 0.015, 0.02]
    print("  deadline | " + "   ".join(f"r={r*100:>4.2f}%" for r in risks))
    for nm, T in [("2wk",10),("3wk",15),("4wk",20),("6wk",30),("8wk",40),("12wk",60)]:
        cells = []
        for r in risks:
            m = ftmo.run_mc(days, r, T, n_paths=40000, seed=5)
            cells.append(f"{m['pass_rate']*100:4.0f}/{m['blow_rate']*100:>2.0f}")
        print(f"  {nm:>7}  | " + "    ".join(cells))
    print("\nHonest read: ~33% pass in 3wk, ~38% in 4wk, ~50% by 8-12wk; blow-up 40-46%.")
    print("80%/3wk is NOT attainable with this (real) edge. Run low risk, expect months.")

if __name__ == "__main__":
    main()
