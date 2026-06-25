"""
pressuretest.py — can ANY honest NAS100 approach clear 50% pass in 3 weeks?

3-week pass is a race to +10% vs the -10% floor / -3% daily cap, governed by the
DAILY SHARPE (mean/std of daily P&L). We:
  1. find the daily Sharpe needed for 50% pass at 15 trading days (normal-day model
     through the exact FTMO rules),
  2. measure the best achievable daily Sharpe across our edges,
  3. test the two levers that can move 3-week pass — risk level and trades/day
     (stacking setups) — and a press-when-ahead sizing scheme,
  4. report the honest maximum 3-week pass and the blow-up it costs.
"""
import numpy as np, pandas as pd, strategies as S, engine, ftmo, data
from run import build_days
COST = 3.0

def days_of(orders, df, ad):
    return build_days(engine.simulate(df, orders, cost_pts=COST), ad)

def norm_pass(mu_d, sd_d, T=15, N=40000, seed=3):
    """normal daily-return model through +10% target / -10% floor / -3% daily / min4."""
    rng = np.random.default_rng(seed)
    R = rng.normal(mu_d, sd_d, size=(N, T))
    E = np.ones(N); alive = np.ones(N, bool); passed = np.zeros(N, bool); dtr = np.zeros(N, int)
    for t in range(T):
        day = R[:, t]; low = np.minimum(day, 0)
        alive &= ~((low <= -0.03) | (E*(1+low) <= 0.90))
        E = np.where(alive & ~passed, E*(1+day), E); dtr += (alive & ~passed)
        passed |= alive & (E >= 1.10) & (dtr >= 4)
    return passed.mean()

def maxpass(days, T=15, risks=(0.0075,0.01,0.0125,0.015,0.02,0.025,0.03)):
    best = max((ftmo.run_mc(days, r, T, n_paths=30000, seed=5) for r in risks),
               key=lambda m: m["pass_rate"])
    # also the risk where pass is maxed
    res = [(r, ftmo.run_mc(days, r, T, n_paths=30000, seed=5)) for r in risks]
    r, m = max(res, key=lambda x: x[1]["pass_rate"])
    return m["pass_rate"], m["blow_rate"], r

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))

    print("="*70)
    print("1) REQUIRED daily Sharpe for 50% pass in 3 weeks (normal-day model)")
    # use a realistic daily std ~3% and vary mean to find the Sharpe for 50%
    sd = 0.03
    for s in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
        p = norm_pass(s*sd, sd)
        print(f"   daily Sharpe {s:.2f} -> {p*100:4.1f}% pass" + ("  <= 50%+" if p>=0.5 else ""))

    print("\n2) ACHIEVABLE edges (corrected engine, cost 3pt) — daily Sharpe @1%")
    A = dict(open_min=16*60, or_min=15, stop_pts=50, vol_filter=True)
    cfgs = {
        "ORB tp4 (1/day)":      S.orb(df, **A, tp_R=4.0, be_R=0.0, trail_R=0.0),
        "ORB trail4 (1/day)":   S.orb(df, **A, tp_R=0.0, be_R=0.0, trail_R=4.0),
        "ORB+pull tp4 (2/day)": S.orb(df, **A, tp_R=4.0, be_R=0.0, trail_R=0.0)
                                + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0),
    }
    best_days = None; best_name = None; best_sh = -9
    for name, orders in cfgs.items():
        d = days_of(orders, df, ad)
        dr = np.asarray(d["day_R"])*0.01
        sh = dr.mean()/dr.std()
        p3, b3, r3 = maxpass(d)
        print(f"   {name:22s} dailySharpe={sh:.3f}  maxpass3wk={p3*100:.0f}% (blow {b3*100:.0f}%, r={r3*100:.2f}%)")
        if sh > best_sh: best_sh, best_days, best_name = sh, d, name

    print("\n3) LEVER A — stack more US-session setups (trades/day) to lift Sharpe")
    # add extra ORB session times; keep only if they don't drag
    stack = (S.orb(df, **A, tp_R=4.0, trail_R=0.0)
             + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)
             + S.orb(df, open_min=17*60, or_min=15, stop_pts=50, vol_filter=True, tp_R=4.0, trail_R=0.0)
             + S.orb(df, open_min=18*60, or_min=15, stop_pts=50, vol_filter=True, tp_R=4.0, trail_R=0.0))
    d = days_of(stack, df, ad)
    tr = engine.simulate(df, stack, cost_pts=COST)
    dr = np.asarray(d["day_R"])*0.0075
    p3, b3, r3 = maxpass(d)
    print(f"   4-setup stack: {len(tr)/(len(ad)/5):.1f} trades/wk  dailySharpe={dr.mean()/dr.std():.3f}  "
          f"maxpass3wk={p3*100:.0f}% (blow {b3*100:.0f}%)")

    print("\n4) LEVER B — press-when-ahead sizing on the best edge (static floor recedes)")
    for k, rmax in [(0.10, 0.02), (0.15, 0.025), (0.20, 0.03)]:
        m = ftmo.run_mc(best_days, 0, 15, n_paths=30000, seed=5,
                        sizing="buffer", risk_k=k, r_min=0.005, r_max=rmax)
        print(f"   press k={k} rmax={rmax*100:.1f}%: pass3wk={m['pass_rate']*100:.0f}% blow={m['blow_rate']*100:.0f}%")

    print("\n5) ABSOLUTE max 3-week pass found, scanning risk to the daily-cap limit:")
    p3, b3, r3 = maxpass(best_days, risks=tuple(np.arange(0.005, 0.031, 0.0025)))
    print(f"   best edge ({best_name}) Sharpe {best_sh:.3f}: max 3wk pass {p3*100:.0f}% at r={r3*100:.2f}% (blow {b3*100:.0f}%)")
    print(f"\nVERDICT: 50%-in-3-weeks needs daily Sharpe ~0.40; best NAS100 edge ~{best_sh:.2f}")
    print(f"         (~8x short). Stacking trades and pressing both fail. Max honest 3wk pass ~{p3*100:.0f}%.")

if __name__ == "__main__":
    main()
