"""
v2/run.py — driver: backtest each strategy, run the FTMO Monte-Carlo, print the
scoreboard (WR / 3-week & monthly pass% / blow%). Usage: python3 run.py
"""
import numpy as np, pandas as pd
import data, strategies, engine, ftmo

RISKS = [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025]
WK3, WK4 = 15, 20            # trading days in 3 / 4 weeks
COST = 2.0                   # round-turn points (spread+commission+slippage)

def build_days(trades, all_dates):
    base = pd.DataFrame({"day": all_dates, "day_R": 0.0, "day_min_R": 0.0, "n": 0})
    base = base.set_index("day")
    if len(trades):
        agg = engine.trades_to_days(trades, all_dates).set_index("day")
        base.loc[agg.index, ["day_R", "day_min_R", "n"]] = agg[["day_R", "day_min_R", "n"]].values
    return base.reset_index().to_records(index=False)

def run_strategy(name, fn, params, df, all_dates, verbose=True):
    orders = fn(df, **params)
    trades = engine.simulate(df, orders, cost_pts=COST)
    if len(trades) == 0:
        print(f"  {name:22s} -- no trades"); return None
    es = engine.edge_stats(trades)
    days = build_days(trades, all_dates)
    n_weeks = len(all_dates) / 5.0
    tpw = es["n"] / n_weeks
    # risk sweep at 3-week deadline; pick best pass
    best = None
    for r in RISKS:
        m = ftmo.run_mc(days, r, WK3, n_paths=20000, seed=7)
        if best is None or m["pass_rate"] > best[1]["pass_rate"]:
            best = (r, m)
    r3, m3 = best
    m4 = ftmo.run_mc(days, r3, WK4, n_paths=20000, seed=7)
    if verbose:
        print(f"  {name:22s} n={es['n']:4d} {tpw:4.1f}/wk  WR={es['wr']*100:4.1f}%  "
              f"expR={es['expR']:+.3f} PF={es['pf']:.2f} maxR={es['maxR']:4.1f} | "
              f"r*={r3*100:.2f}%  3wk: pass={m3['pass_rate']*100:4.1f}% blow={m3['blow_rate']*100:4.1f}%  "
              f"4wk: pass={m4['pass_rate']*100:4.1f}% blow={m4['blow_rate']*100:4.1f}%")
    return dict(name=name, **es, tpw=tpw, r=r3,
                pass3=m3["pass_rate"], blow3=m3["blow_rate"],
                pass4=m4["pass_rate"], blow4=m4["blow_rate"],
                med_days=m3["med_days_to_pass"])

def main():
    df = strategies.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print(f"loaded {len(df):,} bars over {len(all_dates)} weekdays "
          f"({pd.Timestamp(all_dates[0]).date()} .. {pd.Timestamp(all_dates[-1]).date()})")
    print("=" * 120)

    battery = [
        ("ORB 30m s60 tp3",      strategies.orb,       dict(or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0)),
        ("ORB 15m s50 tp3",      strategies.orb,       dict(or_min=15, stop_pts=50, tp_R=3.0, be_R=1.0)),
        ("ORfade 30m s40 tp1",   strategies.or_fade,   dict(or_min=30, poke_pts=15, stop_pts=40, tp_R=1.0)),
        ("ORfade 30m s40 tp1.5", strategies.or_fade,   dict(or_min=30, poke_pts=15, stop_pts=40, tp_R=1.5)),
        ("VWAPfade k2 s50 tp1",  strategies.vwap_fade, dict(k=2.0, stop_pts=50, tp_R=1.0)),
        ("VWAPfade k2.5 s50 t1", strategies.vwap_fade, dict(k=2.5, stop_pts=50, tp_R=1.0)),
        ("VWAPfade k2 s40 tp1.5",strategies.vwap_fade, dict(k=2.0, stop_pts=40, tp_R=1.5)),
    ]
    results = []
    for name, fn, params in battery:
        r = run_strategy(name, fn, params, df, all_dates)
        if r: results.append(r)
    print("=" * 120)
    if results:
        best = max(results, key=lambda x: x["pass3"])
        print(f"BEST 3-week pass: {best['name']}  pass={best['pass3']*100:.1f}%  "
              f"blow={best['blow3']*100:.1f}%  WR={best['wr']*100:.1f}%  r={best['r']*100:.2f}%")

if __name__ == "__main__":
    main()
