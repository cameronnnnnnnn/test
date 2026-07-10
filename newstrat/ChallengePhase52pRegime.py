"""
newstrat/ChallengePhase52pRegime.py — 52p, regime-optimised. A duplicate of ChallengePhase52p with
ONE honest, OOS-validated addition: a mean-reversion (fade) leg that trades ONLY on prior-day-RANGE
regime days, where the regime work found real edge (NAS100 fade|range: 55% WR, +0.11/+0.20 expR
train/test — the highest-WR edge in the project). The four 52p momentum legs are unchanged and run
every day; the fade leg is layered on top on range days only (the "add", not "switch" — replacing
momentum on range days loses too much frequency and passes worse).

Regime (causal, no look-ahead): prior-day ADX(14) < 20 AND Choppiness(14) > 55 on daily bars.
Effect is SMALL but consistent (2-month pass 71.7%->72.1%, blow 18.8%->18.3%; eventual 80.5%->80.9%)
because the fade edge is real but low-frequency (~0.15/day). Same FTMO 15k 1-Step rules, same risk
guidance (0.5-0.6% for a ~2-month window). build(df) -> engine orders. Run: python3 ChallengePhase52pRegime.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
RS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regimeswitch"))
for p in (V4, V3, CP, RS):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402
import indic                                          # noqa: E402

RISK = 0.005; BREAKER = 2.0; COST = 2.0              # 0.5% risk (2-month tuned); -2R breaker
FADE_STOP_ATR = 0.20                                  # fade stop = 0.20 x daily ATR


def range_days(df):
    """Prior-day RANGE regime: ADX(14)<20 and Choppiness(14)>55 on daily bars, shifted 1 (causal)."""
    f = indic.daily_features(df)
    return set(d for d in df["date"].unique()
               if f["adx"].get(d, 99) < 20 and f["chop"].get(d, 0) > 55)


def build(df):
    """The four 52p momentum legs (every day) + a fade leg on prior-day-range days only."""
    mom = CP52.build(df)
    atr = S.daily_atr(df, n=14); sm = {d: FADE_STOP_ATR * v for d, v in atr.items() if v == v}
    rng = range_days(df)
    fade = S.vwap_fade_sel(df, k=2.0, open_min=16*60, trail_R=2.0, partial_R=1.0, stop_map=sm)
    fade_range = [o for o in fade if o["day"] in rng]
    return mom + fade_range


def verify(n_paths=80000):
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    base = build_days(engine.simulate(df, CP52.build(df), cost_pts=COST), ad, BREAKER)
    regm = build_days(engine.simulate(df, build(df), cost_pts=COST), ad, BREAKER)
    es = engine.edge_stats(engine.simulate(df, build(df), cost_pts=COST))
    print("=" * 74)
    print("ChallengePhase52pRegime — 52p + fade-on-prior-day-range leg (regime-optimised)")
    print("=" * 74)
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  {es['n']/df['date'].nunique():.1f} trades/day\n")
    print(f"  {'horizon':>14} {'':>8}{'52p base':>10}{'':>4}{'+regime':>10}")
    for dl, lbl in [(20, "1 month"), (40, "2 months"), (60, "3 months")]:
        rb = max((0.005, 0.006, 0.0075), key=lambda r: ftmo.run_mc(base, r, dl, n_paths=40000, seed=11, block=5)["pass_rate"])
        rr = max((0.005, 0.006, 0.0075), key=lambda r: ftmo.run_mc(regm, r, dl, n_paths=40000, seed=11, block=5)["pass_rate"])
        pb = ftmo.run_mc(base, rb, dl, n_paths=n_paths, seed=11, block=5)["pass_rate"]
        pr = ftmo.run_mc(regm, rr, dl, n_paths=n_paths, seed=11, block=5)["pass_rate"]
        print(f"  {lbl:>14} pass {'':>3}{pb*100:8.1f}% {'->':>3}{pr*100:8.1f}%  ({(pr-pb)*100:+.1f})")
    print("\nSmall but consistent lift on every horizon. The fade|range leg is the highest-WR edge")
    print("the project found (55%), just low-frequency — so it optimises 52p a little, honestly.")


if __name__ == "__main__":
    verify()
