"""
recommended.py — honest, bug-checked strategy for the FTMO $15k 1-Step on NAS100.

History of corrections (why earlier numbers were wrong):
  * engine booked partial-strategy losses at a fraction of -1R (inflated scale-out)
  * exit-search script leaked orb() defaults (tp_R=3,be_R=1) into "trail" configs
Both fixed. After an exhaustive exit search (exitsearch.py) over breakeven, scale-out
and fixed-RR exits with the corrected engine, the differences are small and the edge
is THIN. The best for a fast pass is a hard ~4R take-profit.

Strategy: US Opening-Range Breakout (16:00 server, 15m range, 50pt stop, volume-
confirmed) + VWAP trend-pullback (40pt stop), each with a HARD 4R take-profit, no
trail / BE / scale-out. One trade/day per setup, US session, flat 22:55, Fridays on.

HONEST expectation: expR ~+0.05-0.07R, WR ~30%. ~35% pass in 3 weeks, ~38% in 4,
~50% by 8 weeks, with 40-50% blow-up at the pass-maximising risk. This is a real but
WEAK edge; 80% is not attainable. Run low risk over many attempts.
Run: python3 recommended.py
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

SETUP_A = dict(open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
               tp_R=4.0, be_R=0.0, trail_R=0.0)
SETUP_B = dict(stop_pts=40, tp_R=4.0, trail_R=0.0)   # vwap_pullback has no be_R
COST = 3.0

def orders(df):
    return sorted(S.orb(df, **SETUP_A) + S.vwap_pullback(df, **SETUP_B),
                  key=lambda o: o["entry_bar"])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, orders(df), cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    print("="*70)
    print("RECOMMENDED (bug-checked) — NAS100 ORB + VWAP-pullback, hard 4R TP")
    print("="*70)
    print(f"trades {es['n']} ({es['n']/(len(ad)/5):.1f}/wk)  WR {es['wr']*100:.1f}%  "
          f"expR {es['expR']:+.3f}  PF {es['pf']:.2f}  (cost {COST:.0f}pt)")
    print("\npass% / blow%  by deadline x per-trade risk:")
    risks = [0.0075, 0.01, 0.0125, 0.015, 0.02]
    print("  deadline | " + "   ".join(f"r={r*100:>4.2f}%" for r in risks))
    for nm, T in [("2wk",10),("3wk",15),("4wk",20),("6wk",30),("8wk",40),("12wk",60)]:
        cells = [f"{ftmo.run_mc(days, r, T, n_paths=40000, seed=5)['pass_rate']*100:4.0f}/"
                 f"{ftmo.run_mc(days, r, T, n_paths=40000, seed=5)['blow_rate']*100:>2.0f}"
                 for r in risks]
        print(f"  {nm:>7}  | " + "    ".join(cells))
    print("\nHonest read: ~35% pass in 3wk, ~38% in 4wk, ~50% by 8wk. Thin edge,")
    print("40-50% blow-up at pass-max risk. 80% is NOT attainable. Low risk, many attempts.")

if __name__ == "__main__":
    main()
