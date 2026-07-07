"""
challengephaseHF/fx_mix.py — mix-and-match across instruments. The promising angle: forex
majors are far less correlated with NAS100 than NAS100 setups are with each other, so
stacking them on ONE account should smooth the daily P&L (fewer 3% daily-cap blows) and
raise the monthly pass rate above the NAS100-only 52%.

Applies the setup templates (session ORB + VWAP pullback) to each forex pair with
ATR-SCALED stops (0.2x daily ATR, so a 4R target is a hittable ~0.8x ATR) and per-instrument
spread cost. Reports per-instrument edge + standalone 20-day pass, the cross-instrument
daily-return correlation, and the combined multi-instrument portfolio pass. Run: python3 fx_mix.py
"""
import os, sys
import numpy as np, pandas as pd
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import fx_data, ChallengePhase52p as CP52            # noqa: E402
import warnings; warnings.filterwarnings("ignore")

FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]
DEADLINE = 20


def fx_cost(df):                       # round-turn cost in price units ~ 1.5x median spread
    pt = 0.001 if df["close"].iloc[-1] > 50 else 0.00001
    return 1.5 * df["spread"].median() * pt


def fx_orders(df):                     # session ORBs (London 10:00 + NY 16:30) + VWAP pullback, ATR stops
    atr = S.daily_atr(df, n=14)
    stopmap = {d: 0.2 * v for d, v in atr.items() if v == v}
    return (S.orb(df, open_min=10*60,    or_min=30, tp_R=4.0, be_R=1.0, vol_filter=True, stop_map=stopmap)   # London ORB
          + S.orb(df, open_min=16*60+30, or_min=30, tp_R=4.0, be_R=1.0, vol_filter=True, stop_map=stopmap)   # NY ORB
          + S.vwap_pullback(df, tp_R=6.0, trail_R=0.0, open_min=10*60, buf=0.0, stop_map=stopmap))           # London VWAP pull


def day_series(trades, ad):
    d = build_days(trades, ad, 0.0); return np.asarray(d["day_R"], float)


def main():
    print("Loading NAS100 + 4 forex ...")
    nas = S.prep(data.load())
    nas_tr = engine.simulate(nas, CP52.build(nas), cost_pts=2.0)
    inst = {"NAS100": nas_tr}
    dfs = {"NAS100": nas}
    for x in FX:
        df = S.prep(fx_data.load(x)); dfs[x] = df
        inst[x] = engine.simulate(df, fx_orders(df), cost_pts=fx_cost(df))

    # common date axis (server days) across all instruments
    ad = np.array(sorted(set(nas["date"].unique()).intersection(*[set(dfs[x]["date"].unique()) for x in FX])))
    print(f"common trading days: {len(ad)}  ({pd.Timestamp(ad[0]).date()} .. {pd.Timestamp(ad[-1]).date()})\n")

    print("="*76); print("PER-INSTRUMENT edge + standalone 20-day pass (ATR-scaled)"); print("="*76)
    print(f"  {'instr':8} {'/day':>5} {'WR':>6} {'expR':>7} {'PF':>5} | {'standalone pass':>15}")
    dser = {}
    for x, tr in inst.items():
        tr = tr[tr["day"].isin(set(ad))]
        es = engine.edge_stats(tr) if len(tr) else dict(n=0,wr=0,expR=0,pf=0)
        dser[x] = day_series(tr, ad)
        best = -1
        for r in (0.005,0.0075,0.01,0.0125,0.015):
            m = ftmo.run_mc(build_days(tr, ad, 2.0), r, DEADLINE, n_paths=25000, seed=11, block=5)
            best = max(best, m["pass_rate"])
        print(f"  {x:8} {es['n']/len(ad):5.2f} {es['wr']*100:5.1f}% {es['expR']:+.3f} {es.get('pf',0):5.2f} | {best*100:13.1f}%")

    print("\n" + "="*76); print("CROSS-INSTRUMENT daily-return correlation"); print("="*76)
    DR = pd.DataFrame(dser, index=ad); cols = ["NAS100"]+FX
    print("        " + "".join(f"{c[:6]:>8}" for c in cols))
    for c in cols:
        print(f"  {c:7}" + "".join(f"{DR.corr().loc[c,d]:8.2f}" for d in cols))

    print("\n" + "="*76); print("COMBINED PORTFOLIO 20-day pass (one account, all instruments stacked)"); print("="*76)
    def combo_pass(keys, tag):
        tr = pd.concat([inst[k][inst[k]["day"].isin(set(ad))] for k in keys], ignore_index=True)
        best = (-1, None)
        for r in (0.005,0.0075,0.01,0.0125):
            m = ftmo.run_mc(build_days(tr, ad, 2.0), r, DEADLINE, n_paths=40000, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        print(f"  {tag:34} r*={r*100:.2f}% pass={p*100:4.1f}% blow={m['blow_rate']*100:4.1f}% med={m['med_days_to_pass'] if m['med_days_to_pass']==m['med_days_to_pass'] else 0:.0f}d")
    combo_pass(["NAS100"], "NAS100 52p alone")
    combo_pass(["NAS100"]+FX, "NAS100 + all 4 forex")
    combo_pass(FX, "forex only (4 pairs)")
    print("-"*76)
    print("Does cross-instrument diversification beat the NAS100-only 52% (all-data over common days)?")


if __name__ == "__main__":
    main()
