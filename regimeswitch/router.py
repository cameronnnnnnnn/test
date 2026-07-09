"""
regimeswitch/router.py — build the switch around the edges that the regime_edge matrix ACTUALLY
found (not the 88%-pitch fade, which is dead everywhere):
  * BREAKOUT on contraction days  — prior-day Choppiness high (consolidation) -> expansion breakout
  * SWEEP on trending opens        — first-hour Choppiness low (directional) -> sweep-reclaim reversal
All thresholds tuned on TRAIN only (fixes the earlier look-ahead). Reports each gated leg's
edge TRAIN vs TEST (does the in-sample +0.28 survive?), then stacks the survivors on 52p and
Monte-Carlos the 20-day FTMO pass, train/test + 4-fold. Honest verdict vs the 55% baseline.
Run: python3 router.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402
from creative import sweep_reclaim                    # noqa: E402
import indic                                          # noqa: E402

COST = 2.0; BREAKER = 2.0; DEADLINE = 20; NP = 40000
RISKS = (0.005, 0.0075, 0.01, 0.0125)


def split(ad, frac=0.7):
    cut = ad[int(len(ad) * frac)]; return ad[ad <= cut], ad[ad > cut]


def edge(tr, days):
    g = tr[tr["day"].isin(set(days))]
    return engine.edge_stats(g) if len(g) else dict(n=0, expR=0, wr=0)


def gated(tr, keep_days):
    return tr[tr["day"].isin(set(keep_days))]


def mc(days_struct, r):
    return ftmo.run_mc(days_struct, r, DEADLINE, n_paths=NP, seed=11, block=5)


def best_risk(days_struct):
    return max(RISKS, key=lambda r: mc(days_struct, r)["pass_rate"])


def stack_eval(parts, ad, dtr, dte, tag):
    tr = pd.concat(parts, ignore_index=True)
    dtr_s = build_days(tr[tr["day"].isin(set(dtr))], dtr, BREAKER)
    dte_s = build_days(tr[tr["day"].isin(set(dte))], dte, BREAKER)
    r = best_risk(dtr_s)
    mtr, mte = mc(dtr_s, r), mc(dte_s, r)
    # 4-fold
    folds = np.array_split(ad, 4); fps = []
    for f in folds:
        tr_o = np.concatenate([x for x in folds if x[0] != f[0]])
        r_f = best_risk(build_days(tr[tr["day"].isin(set(tr_o))], tr_o, BREAKER))
        fps.append(mc(build_days(tr[tr["day"].isin(set(f))], f, BREAKER), r_f)["pass_rate"])
    print(f"  {tag:38} r*={r*100:4.2f}%  TR {mtr['pass_rate']*100:4.1f}%  "
          f"TE {mte['pass_rate']*100:4.1f}%  blowTE {mte['blow_rate']*100:4.1f}%  "
          f"foldMean {np.mean(fps)*100:4.1f}% foldWorst {np.min(fps)*100:4.1f}%")


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    dtr, dte = split(ad)
    f = indic.daily_features(df)
    ic = indic.intraday_chop(df, start_min=16*60, win_min=60)

    # thresholds tuned on TRAIN only
    chop_tr = f["chop"].reindex(dtr).dropna()
    contraction_cut = chop_tr.quantile(0.60)                    # top 40% chop = consolidation
    ic_tr = pd.Series({d: ic.get(d, np.nan) for d in dtr}).dropna()
    trendopen_cut = ic_tr.quantile(0.40)                        # bottom 40% intraday chop = directional open
    print(f"train-tuned cuts: contraction prior-day chop>{contraction_cut:.1f}, "
          f"trend-open 1h chop<{trendopen_cut:.1f}\n")

    contraction_days = [d for d in ad if f["chop"].get(d, np.nan) > contraction_cut]
    trendopen_days = [d for d in ad if ic.get(d, np.nan) is not None and ic.get(d, np.nan) < trendopen_cut]

    momo = engine.simulate(df, CP52.build(df), cost_pts=COST)
    brk = gated(engine.simulate(df, S.ib_break(df, ib_min=60, stop_pts=60, trail_R=3.0, open_min=16*60),
                                cost_pts=COST), contraction_days)
    swp = gated(engine.simulate(df, sweep_reclaim(df), cost_pts=COST), trendopen_days)

    print("gated-leg edge (does the in-sample regime edge SURVIVE out-of-sample?):")
    for nm, tr in [("52p momentum", momo), ("breakout|contraction", brk), ("sweep|trendopen", swp)]:
        a, t = edge(tr, dtr), edge(tr, dte)
        print(f"  {nm:22} expR ALL {edge(tr, ad)['expR']:+.3f}  TRAIN {a['expR']:+.3f} (n{a['n']})  "
              f"TEST {t['expR']:+.3f} (n{t['n']})")

    print("\n" + "=" * 92)
    print("STACKED 20-day FTMO pass — do the regime-gated legs beat plain 52p (~55%)?  [risk on train]")
    print("=" * 92)
    stack_eval([momo], ad, dtr, dte, "52p baseline")
    stack_eval([momo, brk], ad, dtr, dte, "52p + breakout|contraction")
    stack_eval([momo, swp], ad, dtr, dte, "52p + sweep|trendopen")
    stack_eval([momo, brk, swp], ad, dtr, dte, "52p + breakout + sweep (full switch)")
    print("-" * 92)
    print("Beats 55% only if TEST and foldWorst rise. If the gated legs' TEST expR collapsed vs")
    print("their ALL/TRAIN expR, that +0.28 was small-sample noise and the stack won't hold up.")


if __name__ == "__main__":
    main()
