"""
improve.py — test pre-deployment tweaks against the current 3-setup baseline,
all under the FTMO MC (cost 3pt). Ideas:
  1. ATR-scaled stops  : scale each setup's validated stop by the day's vol regime
                         (wider stop in high vol -> fewer noise stop-outs)
  2. ATR regime filter : skip the most volatile days (daily-cap protection)
  3. HTF trend filter  : take trend setups (A,B) only with the 20-day trend
  4. Fade vol guard    : take the fade (C) only on normal-vol range days
  5. promising combos
"""
import numpy as np, pandas as pd, strategies as S, engine, ftmo, data
from run import build_days

COST = 3.0
def mc(days, T, r=0.01, best=False):
    if best:
        m = max((ftmo.run_mc(days, rr, T, n_paths=30000, seed=5)
                 for rr in [0.0075,0.009,0.01,0.0125]), key=lambda x: x["pass_rate"])
        return m
    return ftmo.run_mc(days, r, T, n_paths=30000, seed=5)

def score(name, orders, df, ad, trades=None):
    if trades is None:
        trades = engine.simulate(df, orders, cost_pts=COST)
    es = engine.edge_stats(trades); days = build_days(trades, ad)
    m3 = mc(days, 15); m4 = mc(days, 20); m4b = mc(days, 20, best=True)
    print(f"  {name:30s} n={es['n']:4d} WR={es['wr']*100:4.1f}% expR={es['expR']:+.3f} | "
          f"r1%: 3wk {m3['pass_rate']*100:4.1f}/{m3['blow_rate']*100:3.1f}  "
          f"4wk {m4['pass_rate']*100:4.1f}/{m4['blow_rate']*100:3.1f} | "
          f"4wk best {m4b['pass_rate']*100:4.1f}/{m4b['blow_rate']*100:3.1f}")
    return trades

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    A = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0, trail_R=3.0,
             vol_filter=True, partial_R=2.0, partial_frac=0.67)
    B = dict(stop_pts=40, trail_R=3.0, partial_R=2.0, partial_frac=0.5)
    C = dict(k=2.0, stop_pts=40, trail_R=2.0, partial_R=1.0, partial_frac=0.5)

    atr = S.daily_atr(df, 14)
    med = np.nanmedian(list(atr.values()))
    vr = {d: (np.clip(a/med, 0.6, 1.8) if a==a else 1.0) for d,a in atr.items()}
    smap = lambda base: {d: base*vr[d] for d in vr}
    # ATR percentile per day for the regime filter
    avals = pd.Series(atr); hi = avals.quantile(0.90)
    # 20-day daily-close SMA trend
    dc = df.groupby("date")["close"].last(); sma = dc.rolling(20).mean().shift(1)
    trend_up = (dc.shift(1) > sma).to_dict()

    print("="*118)
    print("BASELINE vs tweaks (cost 3pt). cols: n, WR, expR | r=1%: 3wk & 4wk pass/blow | 4wk best-risk")
    print("="*118)
    base = S.orb(df, **A) + S.vwap_pullback(df, **B) + S.vwap_fade_sel(df, **C)
    base_tr = score("BASELINE (fixed stops)", base, df, ad)

    # 1) ATR-scaled stops
    atr_orders = (S.orb(df, **A, stop_map=smap(50)) + S.vwap_pullback(df, **B, stop_map=smap(40))
                  + S.vwap_fade_sel(df, **C, stop_map=smap(40)))
    score("1 ATR-scaled stops", atr_orders, df, ad)

    # 2) ATR regime filter: drop trades on the most volatile 10% of days
    keep2 = base_tr[base_tr["day"].map(lambda d: atr.get(d, 0) <= hi)]
    score("2 skip top-10% vol days", None, df, ad, trades=keep2)

    # 3) HTF trend filter on A & B (fade C kept)
    def htf_ok(row):
        if row["tag"] == "fadeR": return True
        up = trend_up.get(row["day"], True)
        return (row["dir"] > 0) == up
    keep3 = base_tr[base_tr.apply(htf_ok, axis=1)]
    score("3 HTF trend filter (A,B)", None, df, ad, trades=keep3)

    # 4) Fade vol guard: drop fade trades on top-30% vol days
    hi30 = avals.quantile(0.70)
    keep4 = base_tr[~((base_tr["tag"]=="fadeR") & (base_tr["day"].map(lambda d: atr.get(d,0)>hi30)))]
    score("4 fade only normal-vol", None, df, ad, trades=keep4)

    # 5) combo: ATR stops + fade vol guard
    atr_tr = engine.simulate(df, atr_orders, cost_pts=COST)
    keep5 = atr_tr[~((atr_tr["tag"]=="fadeR") & (atr_tr["day"].map(lambda d: atr.get(d,0)>hi30)))]
    score("5 ATR stops + fade guard", None, df, ad, trades=keep5)

if __name__ == "__main__":
    main()
