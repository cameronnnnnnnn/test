"""
batch3 — filters, alternate session, and a 2-session COMBO (the only structural
lever that can raise daily Sharpe: stack uncorrelated positive-edge entries so
daily variance falls while drift stays). Also a trend-day range filter.
"""
import numpy as np, pandas as pd
import data, strategies, engine, ftmo
from run import run_strategy, build_days, RISKS, WK3, WK4, COST

def combo(df, calls):
    """Concatenate orders from several strategy calls -> one trade book."""
    orders = []
    for fn, params in calls:
        orders += fn(df, **params)
    orders.sort(key=lambda o: o["entry_bar"])
    return orders

def run_combo(name, calls, df, all_dates):
    orders = combo(df, calls)
    trades = engine.simulate(df, orders, cost_pts=COST)
    if not len(trades):
        print(f"  {name}: no trades"); return None
    es = engine.edge_stats(trades)
    days = build_days(trades, all_dates)
    tpw = es["n"] / (len(all_dates) / 5.0)
    best = None
    for r in RISKS:
        m = ftmo.run_mc(days, r, WK3, n_paths=20000, seed=7)
        if best is None or m["pass_rate"] > best[1]["pass_rate"]:
            best = (r, m)
    r3, m3 = best
    m4 = ftmo.run_mc(days, r3, WK4, n_paths=20000, seed=7)
    print(f"  {name:26s} n={es['n']:4d} {tpw:4.1f}/wk WR={es['wr']*100:4.1f}% "
          f"expR={es['expR']:+.3f} PF={es['pf']:.2f} | r*={r3*100:.2f}% "
          f"3wk pass={m3['pass_rate']*100:4.1f}% blow={m3['blow_rate']*100:4.1f}% "
          f"4wk pass={m4['pass_rate']*100:4.1f}% blow={m4['blow_rate']*100:4.1f}%")
    return dict(name=name, **es, pass3=m3["pass_rate"], blow3=m3["blow_rate"])

def main():
    df = strategies.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print("batch3 — filters / sessions / combos\n" + "=" * 120)

    base = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0, trail_R=3.0)
    # filters on the best base
    run_strategy("US base (o16 or15 s50 trail3)", strategies.orb, base, df, all_dates)
    run_strategy("US +volfilter", strategies.orb, {**base, "vol_filter": True}, df, all_dates)
    run_strategy("US +rangefilter", strategies.orb, {**base, "range_filter": True}, df, all_dates)
    run_strategy("US +vol+range", strategies.orb, {**base, "vol_filter": True, "range_filter": True}, df, all_dates)
    # alternate session: London/EU open ~10:00 server
    run_strategy("London ORB (o10 or15 s50 trl3)", strategies.orb,
                 {**base, "open_min": 10*60}, df, all_dates)
    # combos
    print("-" * 120)
    run_combo("COMBO US16 + London10", [
        (strategies.orb, base),
        (strategies.orb, {**base, "open_min": 10*60})], df, all_dates)
    run_combo("COMBO US16:00 + US16:30", [
        (strategies.orb, base),
        (strategies.orb, {**base, "open_min": 16*60+30})], df, all_dates)
    run_combo("COMBO US16 + US17 + Lon10", [
        (strategies.orb, base),
        (strategies.orb, {**base, "open_min": 17*60}),
        (strategies.orb, {**base, "open_min": 10*60})], df, all_dates)

if __name__ == "__main__":
    main()
