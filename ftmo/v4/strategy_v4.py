"""
v4/strategy_v4.py — FINAL deployable NAS100 strategy for the FTMO $15k 1-Step.
Bug-checked engine (partial-accounting fix + conservative intra-bar trailing).

Best honest monthly (4-week) pass found across the entire v2/v3 search:
  Setup A: US Opening-Range Breakout — 16:00 server, 15-min range, 50pt stop,
           volume-confirmed, HARD 4R take-profit (no trail / BE / scale-out).
  Setup B: VWAP trend-pullback — 40pt stop, HARD 4R take-profit.
  One trade/day per setup, US cash session, flat 22:55 server, Fridays ON.
  Risk 1.0%/trade. Cost modeled 2pt round-turn (FTMO US100.cash spread, commission-free).

Verified result (this file's main):
  ~41% monthly (4-week) pass, MEDIAN 8 days to pass, ~44% blow-up at r=1.0%.
  >50%/4wk is NOT attainable on NAS100 under the 3% daily cap (see v3/RESULTS3.md);
  but ~41% pass is net +EV via the prop-firm convex payoff (capped fee vs realized
  payout). Run low risk over repeated attempts.
Run: python3 strategy_v4.py
"""
import numpy as np, strategies as S, engine, ftmo, data
from run import build_days

SETUP_A = dict(open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
               tp_R=4.0, be_R=0.0, trail_R=0.0)
SETUP_B = dict(stop_pts=40, tp_R=4.0, trail_R=0.0)
COST = 2.0
RISK = 0.01

def orders(df):
    return sorted(S.orb(df, **SETUP_A) + S.vwap_pullback(df, **SETUP_B),
                  key=lambda o: o["entry_bar"])

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, orders(df), cost_pts=COST)
    es = engine.edge_stats(tr); days = build_days(tr, ad)
    print("="*66)
    print("v4 FINAL — NAS100 ORB + VWAP-pullback, hard 4R TP, r=1.0%")
    print("="*66)
    print(f"trades {es['n']} ({es['n']/(len(ad)/5):.1f}/wk)  WR {es['wr']*100:.1f}%  "
          f"expR {es['expR']:+.3f}  PF {es['pf']:.2f}  (cost {COST:.0f}pt)")
    print("\n monthly (4-week) and other deadlines, r=1.0%:")
    for nm, T in [("2wk",10),("3wk",15),("4wk",20),("6wk",30),("8wk",40)]:
        m = ftmo.run_mc(days, RISK, T, n_paths=50000, seed=5)
        print(f"   {nm:>4}: pass {m['pass_rate']*100:4.1f}%   blow {m['blow_rate']*100:4.1f}%"
              f"   median days-to-pass {m['med_days_to_pass']}")
    print("\n risk sensitivity at 4 weeks:")
    for r in [0.0075, 0.01, 0.0125]:
        m = ftmo.run_mc(days, r, 20, n_paths=50000, seed=5)
        print(f"   r={r*100:.2f}%: pass {m['pass_rate']*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%  "
              f"medDays {m['med_days_to_pass']}")

if __name__ == "__main__":
    main()
