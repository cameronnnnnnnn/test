"""
challengephaseHF/ChallengePhase52p.py — the canonical best challenge strategy of the project.

The highest 20-day (one month) FTMO pass rate found: ~52% all-data, ~44% out-of-sample,
median 9 days. NAS100 (US100) M1. It is a HIGH-RR / LOW-FREQUENCY / UNCORRELATED-STACK
structure (the variance-play optimum), not a low-RR/high-WR one. Four legs + a -2R daily
circuit breaker, 1% risk:

  A  US-open ORB   : 16:00 server, 15-min opening range, 50pt stop, 4R hard TP, vol-confirmed
  B  EU-open ORB   : 11:00 server, 30-min opening range, 50pt stop, 4R hard TP, BE@1R, vol
  C  VWAP pullback : US session, dip to session VWAP in a trend, 40pt stop, hard 6R TP
  D  PDH/PDL break : prior-day high/low breakout, 60pt stop, 3R trailing stop

Edge: WR 26.8%  expR +0.089  PF 1.14  ~3.8 trades/day. The legs are largely uncorrelated
(different sessions + mechanisms), which is what keeps the combined daily P&L smooth enough
to rarely trip the 3% daily cap. FTMO 15k 1-Step rules: +10% target, 10% static floor, 3%
daily, 50% consistency, min 4 days. build(df) -> engine orders. Run: python3 ChallengePhase52p.py
"""
import os, sys
import numpy as np, pandas as pd
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402

RISK = 0.01          # per-trade risk (fraction of balance)
BREAKER = 2.0        # -2R daily circuit breaker (halt new entries once day down 2R)
COST = 2.0           # round-turn cost (index points)
DEADLINE = 20        # trading days (one month)


def build(df):
    """The four legs, merged into one order list for the ftmo/v4 engine."""
    return (S.orb(df, open_min=16*60,    or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True)   # A US ORB
          + S.orb(df, open_min=11*60,    or_min=30, stop_pts=50, tp_R=4.0, be_R=1.0, vol_filter=True)   # B EU ORB
          + S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0)                                     # C VWAP pullback
          + S.pdh_pdl(df, stop_pts=60, trail_R=3.0))                                                    # D PDH/PDL


def verify(n_paths=100000):
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, build(df), cost_pts=COST); es = engine.edge_stats(tr)
    cut = ad[int(len(ad)*0.7)]; te = ad[ad > cut]
    def mc(u):
        d = build_days(tr[tr["day"].isin(set(u))], u, BREAKER)
        return ftmo.run_mc(d, RISK, DEADLINE, n_paths=n_paths, seed=11, block=5)
    print("=" * 74)
    print("ChallengePhase52p — NAS100, 4 legs (US-ORB 4R + EU-ORB 4R + VWpull 6R + PDHL),")
    print(f"-2R daily breaker, {RISK*100:.0f}% risk, {DEADLINE}-day (monthly) FTMO 1-Step pass")
    print("=" * 74)
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  PF {es['pf']:.2f}  "
          f"{es['n']/df['date'].nunique():.1f} trades/day  ({es['n']} trades)")
    for lbl, u in [("ALL data ", ad), ("TEST(OOS)", te)]:
        m = mc(u); md = m["med_days_to_pass"]
        print(f"  [{lbl}] MONTHLY pass {m['pass_rate']*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%  "
              f"timeout {m['timeout_rate']*100:4.1f}%  median {md if md==md else 0:.0f}d")


if __name__ == "__main__":
    verify()
