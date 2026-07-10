"""
newstrat/regime_matrix.py — iteration 2: the user's regime idea, done honestly. Detect the regime
from the PRIOR day's data (causal — regimes persist), then see which setup actually earns its keep
in each regime, per instrument. This is the foundation for a regime router: a setup only gets to
"own" a regime if it is +EV OUT-OF-SAMPLE there (train picks, test confirms), not just in-sample.

Regime (prior-day, standard untuned thresholds on that instrument's daily bars):
  trend  = ADX>=25 and Choppiness<45   |  range = ADX<20 and Choppiness>55  |  else unclear
Setups (high-RR, since iteration 1 killed low-RR): momentum ORB(4R), open-drive(trail), fade(MR).
Reports expR TRAIN/TEST + n per (instrument, setup, regime). Run: python3 regime_matrix.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
RS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regimeswitch"))
for p in (V4, RS):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine                        # noqa: E402
import allinstr                                       # noqa: E402
import indic                                          # noqa: E402

SESS = {"NAS100": 16*60, "EURUSD": 10*60, "GBPUSD": 10*60, "AUDUSD": 10*60, "USDJPY": 0}
REGIMES = ["trend", "range", "unclear"]


def regime_map(df):
    f = indic.daily_features(df)          # causal (shifted 1 day) ADX/chop
    out = {}
    for dt in df["date"].unique():
        r = f.loc[dt] if dt in f.index else None
        if r is None or r["adx"] != r["adx"] or r["chop"] != r["chop"]:
            out[dt] = "unclear"
        elif r["adx"] >= 25 and r["chop"] < 45:
            out[dt] = "trend"
        elif r["adx"] < 20 and r["chop"] > 55:
            out[dt] = "range"
        else:
            out[dt] = "unclear"
    return out


def setups(df, omin, sm):
    # momentum vs mean-reversion — the opposing pair a regime router routes between.
    # both ATR-scaled via stop_map so they work cleanly on every instrument.
    return {
        "mom4R": S.orb(df, open_min=omin, or_min=30, tp_R=4.0, be_R=0.0, vol_filter=True, stop_map=sm),
        "fade":  S.vwap_fade_sel(df, k=2.0, open_min=omin, trail_R=2.0, partial_R=1.0, stop_map=sm),
    }


def split(dates):
    ad = np.array(sorted(dates)); cut = ad[int(len(ad)*0.7)]
    return set(ad[ad <= cut]), set(ad[ad > cut])


def main():
    print("Loading all instruments ...")
    D = allinstr.load_all(verbose=False)
    print("\n" + "=" * 92)
    print("EDGE by PRIOR-DAY REGIME x SETUP x INSTRUMENT — expR TRAIN / TEST (n)   [pick on train, confirm on test]")
    print("=" * 92)
    for x in allinstr.ALL:
        info = D[x]; df = info["df"]; sm = allinstr.stopmap(info, 0.20)
        rmap = regime_map(df); dtr, dte = split(df["date"].unique())
        from collections import Counter
        cnt = Counter(rmap.values())
        print(f"\n{x}  (regime days: trend {cnt['trend']}, range {cnt['range']}, unclear {cnt['unclear']})")
        print(f"  {'setup':7}" + "".join(f"{r:>22}" for r in REGIMES))
        for name, orders in setups(df, SESS[x], sm).items():
            tr = engine.simulate(df, orders, cost_pts=info["cost"])
            if len(tr):
                tr = tr.copy(); tr["reg"] = tr["day"].map(rmap)
            row = f"  {name:7}"
            for reg in REGIMES:
                g = tr[tr["reg"] == reg] if (len(tr) and "reg" in tr.columns) else tr.iloc[0:0]
                if len(g) and "day" in g.columns:
                    gtr = g[g["day"].isin(dtr)]; gte = g[g["day"].isin(dte)]
                    etr = engine.edge_stats(gtr)["expR"] if len(gtr) else float("nan")
                    ete = engine.edge_stats(gte)["expR"] if len(gte) else float("nan")
                else:
                    etr = ete = float("nan")
                cell = f"{etr:+.2f}/{ete:+.2f} n{len(g)}"
                row += f"{cell:>22}"
            print(row)
    print("\n" + "-" * 92)
    print("A setup 'owns' a regime only if BOTH train and test expR are clearly +. Same sign both")
    print("halves = real; sign flip train->test = noise (small n). That mapping -> the router (iter 3).")


if __name__ == "__main__":
    main()
