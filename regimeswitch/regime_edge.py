"""
regimeswitch/regime_edge.py — the DECISIVE honest test before building any switch: does each
strategy's edge actually depend on the regime? Tags every trade with its day's regime (both a
prior-day daily read AND an intraday first-hour read) and reports expectancy per bucket.

If regime-conditioning is real we should SEE:
  * momentum (52p legs) expR high in TREND / trendy-open, low or negative in RANGE / choppy-open
  * a FADE leg expR positive in RANGE / choppy-open (even if negative overall)
  * breakout best on EXPANSION, sweep best on REVERSAL
If instead expR is flat across regimes, the regime signal is noise and no switch will help.
Run: python3 regime_edge.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                 # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402
from creative import sweep_reclaim                    # noqa: E402
import indic                                          # noqa: E402

COST = 2.0


def legs(df):
    return {
        "momentum(52p)": CP52.build(df),
        "fade":          S.vwap_fade_sel(df, k=2.0, stop_pts=40, partial_R=1.0, trail_R=2.0)
                         + S.or_fade(df, poke_pts=15, stop_pts=40, tp_R=1.5),
        "breakout(IB)":  S.ib_break(df, ib_min=60, stop_pts=60, trail_R=3.0, open_min=16*60),
        "sweep":         sweep_reclaim(df),
    }


def prior_day_regime(df, ad):
    f = indic.daily_features(df)
    reg = {}
    for dt in ad:
        r = f.loc[dt] if dt in f.index else None
        if r is None or r["adx"] != r["adx"] or r["chop"] != r["chop"]:
            reg[dt] = "unclear"
        elif r["adx"] >= 25 and r["chop"] < 45:
            reg[dt] = "trend"
        elif r["adx"] < 20 and r["chop"] > 55:
            reg[dt] = "range"
        else:
            reg[dt] = "unclear"
    return reg


def intraday_regime(df, ad):
    ic = indic.intraday_chop(df, start_min=16*60, win_min=60)
    s = pd.Series({d: ic.get(d, np.nan) for d in ad}).dropna()
    lo, hi = s.quantile(1/3), s.quantile(2/3)
    reg = {}
    for d in ad:
        v = ic.get(d, np.nan)
        reg[d] = "?" if v != v else ("trendopen" if v <= lo else ("chopopen" if v >= hi else "mid"))
    return reg


def matrix(trades, daymap, order):
    t = trades.copy(); t["reg"] = t["day"].map(daymap)
    cells = {}
    for r in order:
        g = t[t["reg"] == r]
        cells[r] = engine.edge_stats(g) if len(g) else dict(n=0, expR=0, wr=0)
    return cells


def show(title, legdict, daymap, order, ndays_by_reg):
    print("\n" + "=" * 84); print(title); print("=" * 84)
    head = "  " + f"{'strategy':16}" + "".join(f"{r:>16}" for r in order)
    print(head); print(f"  {'days in regime':16}" + "".join(f"{ndays_by_reg.get(r,0):>16}" for r in order))
    for name, orders in legdict.items():
        tr = engine.simulate(_DF, orders, cost_pts=COST)
        cells = matrix(tr, daymap, order)
        row = f"  {name:16}"
        for r in order:
            c = cells[r]
            row += f"  {('exp'+format(c['expR'],'+.3f')):>8} n{c['n']:<5}"
        print(row)


def main():
    global _DF
    _DF = S.prep(data.load()); df = _DF
    ad = np.array(sorted(df["date"].unique()))
    L = legs(df)

    pr = prior_day_regime(df, ad); ir = intraday_regime(df, ad)
    from collections import Counter
    nb_pr = Counter(pr[d] for d in ad); nb_ir = Counter(ir[d] for d in ad)

    show("EDGE BY PRIOR-DAY REGIME (ADX/Choppiness of prior days)", L, pr,
         ["trend", "range", "unclear"], nb_pr)
    show("EDGE BY INTRADAY-OPEN REGIME (first-hour Choppiness of the day itself)", L, ir,
         ["trendopen", "mid", "chopopen"], nb_ir)

    print("\n" + "-" * 84)
    print("What to look for: momentum expR should be HIGHER in trend/trendopen than range/chopopen,")
    print("and the FADE row should go POSITIVE in range/chopopen. If momentum expR barely moves")
    print("across regimes and fade stays negative everywhere, the regime signal has no real edge.")


if __name__ == "__main__":
    main()
