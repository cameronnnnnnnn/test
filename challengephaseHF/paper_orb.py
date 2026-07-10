"""
challengephaseHF/paper_orb.py — test the Concretum (Zarattini-Barbon-Aziz 2024) 5-min ORB mechanics
on NAS100 (US open), since 52p is the same ORB family. The paper's HEADLINE edge (Stocks in Play /
top-20 Relative Volume) is a STOCK-SELECTION edge across 7,000 names and does NOT transfer to a
single index. But three mechanics are testable here:
  (a) 5-min opening range, enter on the break, stop = k*ATR, EOD exit (NO target — paper says targets hurt)
  (b) first-5-min-candle DIRECTION FILTER: only long if the 5-min candle is green, only short if red
Compares plain 5-min ORB vs +direction-filter, at 10%-ATR and 20%-ATR stops. Does the paper's
direction filter add edge on the index? Run: python3 paper_orb.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                 # noqa: E402
from engine import ExitSpec                            # noqa: E402

OPEN = 16 * 60 + 30; SESS_END = 22 * 60 + 55           # US cash open (server EET), EOD flat


def paper_orb(df, stop_map, or_min=5, direction_filter=True, entry_by=21*60):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    orders = []
    or_end = OPEN + or_min
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        orw = gi[(t >= OPEN) & (t < or_end)]
        if len(orw) < or_min - 1:
            continue
        or_open = o[orw[0]]; or_close = c[orw[-1]]
        rh = h[orw].max(); rl = l[orw].min()
        bull = or_close > or_open; bear = or_close < or_open
        if not (bull or bear):
            continue                                   # doji -> no trade (paper rule)
        stp = stop_map.get(day, np.nan)
        if not (stp == stp) or stp <= 0:
            continue
        post = gi[(t >= or_end) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        spec = ExitSpec(tp_R=0.0, be_R=0.0, trail_R=0.0, max_bars=10**9)   # EOD runner, no target
        allow_long = bull or (not direction_filter)
        allow_short = bear or (not direction_filter)
        for b in post[:-1]:
            if tod[b] > entry_by:
                break
            if allow_long and h[b] >= rh:
                orders.append(dict(entry_bar=b, dir=1, stop_pts=stp, spec=spec, eod_bar=eod, day=day, tag="porb")); break
            if allow_short and l[b] <= rl:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stp, spec=spec, eod_bar=eod, day=day, tag="porb")); break
    return orders


def main():
    df = S.prep(data.load()); nd = df["date"].nunique()
    atr = S.daily_atr(df, n=14)
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    dtr, dte = set(ad[ad <= cut]), set(ad[ad > cut])
    print("Concretum 5-min ORB mechanics on NAS100 (US open, EOD runner, no target)\n")
    print(f"  {'stop':>8} {'direction filter':18}{'/day':>6}{'WR':>7}{'expR':>8}{'exp_tr':>8}{'exp_te':>8}")
    for frac in (0.10, 0.20):
        sm = {d: frac * v for d, v in atr.items() if v == v}
        for dfil in (False, True):
            tr = engine.simulate(df, paper_orb(df, sm, direction_filter=dfil), cost_pts=2.0)
            if not len(tr):
                continue
            e = engine.edge_stats(tr)
            etr = engine.edge_stats(tr[tr['day'].isin(dtr)])['expR'] if len(tr[tr['day'].isin(dtr)]) else float('nan')
            ete = engine.edge_stats(tr[tr['day'].isin(dte)])['expR'] if len(tr[tr['day'].isin(dte)]) else float('nan')
            lab = "ON (paper rule)" if dfil else "off (both sides)"
            print(f"  {frac*100:6.0f}% {lab:18}{e['n']/nd:6.2f}{e['wr']*100:6.1f}%{e['expR']:+8.3f}{etr:+8.3f}{ete:+8.3f}")
    print()
    # 52p reference
    import ChallengePhase52p as CP52
    e = engine.edge_stats(engine.simulate(df, CP52.build(df), cost_pts=2.0))
    print(f"  52p reference: {e['n']/nd:.2f}/day  WR {e['wr']*100:.1f}%  expR {e['expR']:+.3f}")
    print("\nDoes the paper's first-candle DIRECTION FILTER add edge vs taking both sides? And does the")
    print("tight 10%-ATR stop beat 20%? If the filter lifts expR and holds train->test, it's worth")
    print("folding into 52p; if it's flat/noise, the paper's edge really was the stock selection.")


if __name__ == "__main__":
    main()
