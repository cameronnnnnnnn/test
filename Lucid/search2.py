"""
Lucid/search2.py — round 2: tune the high-edge ORB/trend family + the new levers
(self-imposed daily stop, dynamic buffer-sizing) to push monthly pass rate.

Run: python3 search2.py
"""
import numpy as np, pandas as pd
import data, strategies as S, engine, lucid

COST = 1.0
DEADLINE = 21
NP = 30000
FIX_RISKS = [75, 100, 125, 150, 175, 200, 250, 300]
DAILY_STOPS = [0.0, 2.0, 3.0]
BUF_K = [0.20, 0.30, 0.40]
BUF_MAX = [300.0, 400.0]

def best_for(orders, df, all_dates, stop_hint):
    """Sweep daily-stop x sizing x risk; return the best (max pass) variant."""
    trades = engine.simulate(df, orders, cost_pts=COST)
    if len(trades) == 0:
        return None
    es = engine.edge_stats(trades)
    best = None
    for ds in DAILY_STOPS:
        days = lucid.build_days(trades, all_dates, daily_stop_R=ds)
        # fixed sizing
        for rd in FIX_RISKS:
            if lucid.micros_for(rd, stop_hint) > 20.0+1e-9: continue
            m = lucid.run_eval_mc(days, rd, DEADLINE, n_paths=NP, seed=7)
            tag = f"ds{ds:.0f} fix${rd:.0f}({lucid.micros_for(rd,stop_hint):.1f}m)"
            if best is None or m["pass_rate"] > best[2]["pass_rate"]:
                best = (tag, ds, m)
        # buffer sizing
        for k in BUF_K:
            for rmax in BUF_MAX:
                m = lucid.run_eval_mc(days, 0, DEADLINE, n_paths=NP, seed=7,
                                      sizing="buffer", k=k, rd_min=50.0, rd_max=rmax)
                tag = f"ds{ds:.0f} buf k{k:.2f}/${rmax:.0f}"
                if best is None or m["pass_rate"] > best[2]["pass_rate"]:
                    best = (tag, ds, m)
    return es, best

def main():
    df = S.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print(f"loaded {len(df):,} bars, {len(all_dates)} weekdays. COST={COST}pt, monthly={DEADLINE}d, {NP} paths")
    print("="*120)

    cfgs = []
    # ORB family grid (the round-1 winner family)
    for om in [945, 960, 990]:
        for orm in [15, 30, 45]:
            for stop in [50, 60, 75]:
                for tp in [3.0, 4.0]:
                    cfgs.append((f"ORB o{om} {orm}m s{stop} tp{tp:.0f}",
                                 S.orb(df, open_min=om, or_min=orm, stop_pts=stop, tp_R=tp, be_R=1.0, vol_filter=True), stop))
    # trail + long-only variants of the best shape
    for stop in [50, 60]:
        cfgs.append((f"ORB o960 30m s{stop} tr3", S.orb(df, open_min=960, or_min=30, stop_pts=stop, tp_R=0.0, be_R=1.0, trail_R=3.0, vol_filter=True), stop))
        cfgs.append((f"ORB o960 30m s{stop} tp3 LONG", S.orb(df, open_min=960, or_min=30, stop_pts=stop, tp_R=3.0, be_R=1.0, long_only=True, vol_filter=True), stop))
    # combo of the two best edges
    cfgs.append(("ORB30+VWpull tp3",
        S.orb(df, open_min=960, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
        + S.vwap_pullback(df, stop_pts=40, tp_R=3.0), 50))

    rows = []
    for name, orders, stop in cfgs:
        r = best_for(orders, df, all_dates, stop)
        if r is None:
            continue
        es, (tag, ds, m) = r
        rows.append((name, es, tag, m))
        print(f"  {name:26s} n={es['n']:4d} WR={es['wr']*100:4.1f}% expR={es['expR']:+.3f} | "
              f"{tag:20s} PASS={m['pass_rate']*100:4.1f}% blow={m['blow_rate']*100:4.1f}% "
              f"to={m['timeout_rate']*100:4.1f}% med={m['med_days']:.0f}d")
    print("="*120)
    rows.sort(key=lambda x: x[3]["pass_rate"], reverse=True)
    print("TOP 10 by MONTHLY PASS RATE:")
    for name, es, tag, m in rows[:10]:
        print(f"  {name:26s} {tag:22s} PASS={m['pass_rate']*100:4.1f}%  blow={m['blow_rate']*100:4.1f}%  "
              f"to={m['timeout_rate']*100:4.1f}%  WR={es['wr']*100:4.1f}%  expR={es['expR']:+.3f}  med={m['med_days']:.0f}d")

if __name__ == "__main__":
    main()
