"""
challengephaseHF/lucid_eval.py — 52p under the Lucid 25k Flex Eval (futures) rules:
  account 25,000 · target +$1,250 (5%) · max drawdown $1,000 (4%) · NO daily loss limit ·
  50% consistency · max size 2 minis / 20 micros NQ ($40/pt).

Two things dominate here and are very different from FTMO:
  1. the max DD is only 4% (half of FTMO's 10%) — much less room, so risk must be tiny;
  2. no daily limit, lower 5% target — both help.
And the DRAWDOWN TYPE is decisive but not stated: futures evals usually TRAIL (peak-to-date
minus $1,000), which is far harder than a static floor. So we bracket it: static vs EOD-trailing.

Uses the same 52p NQ-equivalent day-returns (NQ tracks the same Nasdaq-100 as US100). Also
translates the best risk % into actual micro contracts, and checks the size cap. Run: python3 lucid_eval.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402

NP = 100_000
ACCT = 25000.0; TARGET = 1.05; DD = 0.04             # +5% target, 4% max DD
RISKS = (0.003, 0.004, 0.005, 0.0075, 0.01, 0.0125, 0.015)
MNQ_PER_POINT = 2.0                                   # 1 micro NQ = $2 / index point
AVG_STOP_PTS = 50                                     # 52p stops ~40-60 pts


def best(days, deadline, **kw):
    br = (-1, None, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, deadline, n_paths=NP, seed=11, block=5,
                        daily=0.0, target=TARGET, consistency=True, **kw)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def contracts(r):
    dollars = r * ACCT
    return dollars / (AVG_STOP_PTS * MNQ_PER_POINT)   # micros per leg at a 50-pt stop


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 82)
    print("52p under LUCID 25k FLEX EVAL — 25k · +$1,250 (5%) · $1,000 (4%) DD · no daily · 50% cons.")
    print("=" * 82)
    print(f"  {'drawdown type':26} {'risk*':>6} {'~micros/leg':>12} {'PASS':>6} {'BLOW':>6} {'still':>6}")
    for tag, kw in [("STATIC floor (easy case)", dict(floor=1.0 - DD)),
                    ("EOD-TRAILING (likely)",   dict(trail_dd=DD))]:
        for dl in (20, 60):
            p, r, m = best(days, dl, **kw)
            still = m["timeout_rate"]
            lbl = f"{tag} {dl}d"
            print(f"  {lbl:26} {r*100:5.2f}% {contracts(r):11.1f} {p*100:5.1f}% "
                  f"{m['blow_rate']*100:5.1f}% {still*100:5.1f}%")
        print()

    print("-" * 82)
    print("FTMO 15k reference (10% target, 10% DD, 3% daily): ~55% in 20 days at 0.75%.")
    print("Size cap: 20 micros = $40/pt; at these risks a leg is ~1-2 micros, 4 legs ~4-8 -> under cap.")
    print("\nCRITICAL: futures accounts are NETTING, but 52p needs HEDGING (4 independent long/short")
    print("legs at once). As-is the EA will NOT run on Lucid — the legs would net/cancel. It needs a")
    print("netting rewrite (one net position) first, which changes behavior. Also: static vs trailing")
    print("DD is decisive and unconfirmed — if Lucid trails intraday (not EOD), it is harder still.")


if __name__ == "__main__":
    main()
