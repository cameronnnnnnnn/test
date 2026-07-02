"""
challengephasev3/sortino.py — Sortino (and Sharpe, for contrast) for the strat you run:
live combo = ORB 50 4R + VWpull 40 4R. Sortino = mean / downside-deviation (MAR=0), so
it only penalises DOWNSIDE vol — it rewards the fat 4R winners instead of punishing them
like Sharpe does. Scale-invariant to risk %, so it's a property of the strategy, not sizing.

Reports per-trade and per-trading-day (annualised x sqrt(252)), plus your live 6-trade
account number (flagged as not statistically meaningful). Run: python3 sortino.py
"""
import os, sys
import numpy as np
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine
import search as SR


def sortino(x, mar=0.0):
    x = np.asarray(x, float); dn = np.minimum(x - mar, 0.0)
    dd = np.sqrt(np.mean(dn**2))
    return (x.mean() - mar) / dd if dd > 0 else np.inf, dd


def sharpe(x):
    x = np.asarray(x, float); s = x.std(ddof=1)
    return x.mean() / s if s > 0 else np.inf


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    o = (S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, trail_R=0.0, vol_filter=True)
         + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0))
    tr = engine.simulate(df, o, cost_pts=2.0)
    R = tr["R"].values
    d = SR.build_days(tr, ad, 0.0); dayR = np.asarray(d["day_R"], float)   # all weekdays incl flat
    active = dayR[np.asarray(d["n"]) > 0]

    print("=" * 78)
    print("SORTINO — live combo (ORB 50 4R + VWpull 40 4R)  [backtest, the meaningful one]")
    print("=" * 78)
    st_t, dd_t = sortino(R); print(f"  per-TRADE   : Sortino {st_t:5.2f}   Sharpe {sharpe(R):5.2f}   "
                                   f"(n={len(R)}, mean {R.mean():+.3f}R, downside-dev {dd_t:.3f}R)")
    st_d, dd_d = sortino(dayR)
    print(f"  per-DAY     : Sortino {st_d:5.2f}   Sharpe {sharpe(dayR):5.2f}   "
          f"(all {len(dayR)} weekdays incl. flat; mean {dayR.mean():+.3f}R)")
    print(f"  ANNUALISED  : Sortino {st_d*np.sqrt(252):5.1f}   Sharpe {sharpe(dayR)*np.sqrt(252):5.1f}   "
          f"(x sqrt(252))")
    st_a, _ = sortino(active)
    print(f"  per ACTIVE day: Sortino {st_a:5.2f}   Sharpe {sharpe(active):5.2f}   (only days with a trade)")
    print("-" * 78)
    print("  Sortino > Sharpe here because the +4R winners are UPSIDE vol — Sharpe punishes")
    print("  them, Sortino doesn't. That gap is the whole point of a positive-skew strategy.")
    print("=" * 78)

    # your actual account, 6 trades (NOT statistically meaningful)
    acct_R = np.array([-148.05, -157.77, -148.61, 588.82, -151.25, 594.69]) / 150.0
    day_pnl = np.array([-305.82, 440.21, 443.44]) / 15000.0 * 100   # 3 trading days, % of $15k
    st_acc, _ = sortino(acct_R); st_dacc, _ = sortino(day_pnl)
    print("YOUR LIVE ACCOUNT (6 trades / 3 days) — shown for fun, NOT statistically valid:")
    print(f"  per-trade Sortino {st_acc:.2f}  ·  per-day Sortino {st_dacc:.2f}  "
          f"(n=6 / 3 — way too small; the backtest numbers above are your real expectation)")


if __name__ == "__main__":
    main()
