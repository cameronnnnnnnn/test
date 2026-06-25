"""
v2/tune.py — run an arbitrary list of (name, fn, params) through the same
backtest+MC pipeline as run.py and print a sorted scoreboard. Import and call
tune(configs) or edit the __main__ block.
"""
import sys
import data, strategies, engine
from run import run_strategy
import numpy as np, pandas as pd

def tune(configs, df=None, all_dates=None, sort_key="pass3"):
    if df is None:
        df = strategies.prep(data.load())
        all_dates = np.array(sorted(df["date"].unique()))
    res = []
    for name, fn, params in configs:
        r = run_strategy(name, fn, params, df, all_dates)
        if r:
            res.append(r)
    res.sort(key=lambda x: -x[sort_key])
    print("-" * 120)
    print(f"sorted by {sort_key}:")
    for r in res[:8]:
        print(f"  {r['name']:24s} WR={r['wr']*100:4.1f}% expR={r['expR']:+.3f} "
              f"PF={r['pf']:.2f} | r={r['r']*100:.2f}% 3wk pass={r['pass3']*100:4.1f}% "
              f"blow={r['blow3']*100:4.1f}%  med_days={r['med_days']}")
    return res, df, all_dates

if __name__ == "__main__":
    df = strategies.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print(f"ORB tuning over {len(all_dates)} weekdays\n" + "=" * 120)

    configs = []
    for open_min in [16*60, 16*60+30]:                 # 16:00 vs 16:30 open
        for or_min in [15, 30]:
            for stop in [50, 80]:
                # exit A: hard 3R + breakeven@1R ; exit B: trail 3R no BE
                configs.append((f"ORB o{open_min//60}:{open_min%60:02d} or{or_min} s{stop} tp3be1",
                                strategies.orb,
                                dict(open_min=open_min, or_min=or_min, stop_pts=stop,
                                     tp_R=3.0, be_R=1.0, trail_R=0.0)))
                configs.append((f"ORB o{open_min//60}:{open_min%60:02d} or{or_min} s{stop} trail3",
                                strategies.orb,
                                dict(open_min=open_min, or_min=or_min, stop_pts=stop,
                                     tp_R=0.0, be_R=0.0, trail_R=3.0)))
    tune(configs, df, all_dates)
