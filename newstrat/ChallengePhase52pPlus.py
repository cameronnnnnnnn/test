"""
newstrat/ChallengePhase52pPlus.py — 52p PLUS the four additive keepers (the grand-unification
winner, iteration 9). First combination in the whole project that improves EVERY metric over 52p:

                       TE20    blow    foldMean/worst    40d(all)   blow40
  52p alone            49.2%   31.5%   55.6% / 37.4%     71.5%      11.1%
  52p + NAS/GER pack   54.5%   28.2%   57.3% / 40.2%     74.5%      10.3%

The pack (each leg individually OOS-validated, all pairwise correlations ~0; lifts are additive):
  K1 fade|range   NAS100 VWAP-fade, ONLY on prior-day-range days (ADX<20 & Chop>55, causal)
  K3 ger40_close  GER40 long 18:00->18:45 server (drift into the DAX cash close)
  K4 tom          NAS100 turn-of-month long (last td + first 3 of month), 3R trail
  K5 monday       NAS100 long through the Monday US session, 0.5-ATR stop, EOD exit

USDJPY-Tokyo (K2) is EXCLUDED from the default build: it lifts the worst-fold floor (37->44) but
costs mean pass and doubles 40-day blow (11->22%) — add it only if you want max floor over mean.

Deployment note: needs TWO symbols (NAS100 + GER40). Live 52p account: leave as is — this is for
the NEXT account. Run: python3 ChallengePhase52pPlus.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3"), ("..", "challengephaseHF")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
sys.path.insert(0, HERE)
import data, strategies as S, engine, ftmo, fx_data     # noqa: E402
from engine import ExitSpec                               # noqa: E402
from search import build_days                             # noqa: E402
import ChallengePhase52p as CP52                           # noqa: E402
from creative import tom_long                              # noqa: E402
from regime_matrix import regime_map                       # noqa: E402
from mined import time_leg                                 # noqa: E402

RISK = 0.005; BREAKER = 2.0; COST_NAS = 2.0; COST_GER = 1.5


def monday_leg(df, sm):
    tod = df["tod"].values; orders = []
    spec = ExitSpec(tp_R=0.0, be_R=0.0, trail_R=0.0, max_bars=10**9)
    for day, gi in df.groupby("date").indices.items():
        if pd.Timestamp(day).dayofweek != 0: continue
        t = tod[gi]; sess = gi[(t >= 16*60+30) & (t <= 22*60+55)]
        stp = sm.get(day, np.nan)
        if len(sess) < 100 or not (stp == stp): continue
        orders.append(dict(entry_bar=sess[0], dir=1, stop_pts=stp, spec=spec,
                           eod_bar=sess[-1], day=day, tag="monday"))
    return orders


def build_nas(nas):
    """All NAS100 legs: the four 52p legs + fade|range + tom + monday."""
    aN = S.daily_atr(nas, 14)
    smN20 = {d: 0.20*v for d, v in aN.items() if v == v}
    smN50 = {d: 0.50*v for d, v in aN.items() if v == v}
    rng = set(d for d in nas["date"].unique() if regime_map(nas).get(d) == "range")
    fade = [o for o in S.vwap_fade_sel(nas, k=2.0, open_min=16*60, trail_R=2.0,
                                       partial_R=1.0, stop_map=smN20) if o["day"] in rng]
    return CP52.build(nas) + fade + tom_long(nas) + monday_leg(nas, smN50)


def build_ger(ger):
    """GER40 leg: long into the DAX cash close, 18:00->18:45 server, 0.25-ATR stop."""
    aG = S.daily_atr(ger, 14)
    smG = {d: 0.25*v for d, v in aG.items() if v == v}
    return time_leg(ger, +1, 18*60, 18*60+45, smG, "ger_close")


def trades(nas=None, ger=None):
    nas = nas if nas is not None else S.prep(data.load())
    ger = ger if ger is not None else S.prep(fx_data.load("GER40"))
    t = pd.concat([engine.simulate(nas, build_nas(nas), cost_pts=COST_NAS),
                   engine.simulate(ger, build_ger(ger), cost_pts=COST_GER)], ignore_index=True)
    ad = np.array(sorted(set(nas["date"].unique()) & set(ger["date"].unique())))
    return t[t["day"].isin(set(ad))], ad


def verify(n_paths=100000):
    tr, ad = trades()
    es = engine.edge_stats(tr)
    days = build_days(tr, ad, BREAKER)
    print("=" * 74)
    print("ChallengePhase52pPlus — 52p + fade|range + GER40-close + tom + Monday")
    print("=" * 74)
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  {es['n']/len(ad):.1f} trades/day  ({es['n']} trades, {len(ad)} days)")
    for dl, lbl in [(20, "1 month "), (40, "2 months"), (60, "3 months")]:
        best = (-1, None, None)
        for r in (0.004, 0.005, 0.006, 0.0075):
            m = ftmo.run_mc(days, r, dl, n_paths=n_paths, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        print(f"  [{lbl}] pass {p*100:4.1f}%  blow {m['blow_rate']*100:4.1f}%  (risk {r*100:.2f}%)")


if __name__ == "__main__":
    verify()
