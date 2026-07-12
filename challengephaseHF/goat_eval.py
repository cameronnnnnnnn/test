"""
challengephaseHF/goat_eval.py — GOAT FUNDED "Blitz" 10k, evaluated honestly.

Rules (from the user's screenshot + answers):
  1-STEP.  Profit target +3%.  Max daily loss 3%.  Max total loss 5%.
  No time limit.  No consistency rule.  News + weekend holding allowed.  ~$100 AUD / 10k.
The one unknown the card doesn't state is whether the 5% max loss is STATIC (from the 10k start,
floor 9,500) or TRAILING (peak - 5%). It swings the answer, so both are modelled below.

Why the shape matters: target +3% vs floor -5%. For a driftless (0EV) strategy the eventual pass
odds are ~ floor/(target+floor) = 5/8 = 62.5% (vs FTMO 1-step 10/10 = 50%). With no time limit
the relevant number is the EVENTUAL pass = P(reach +3% before -5%), so we run a long deadline.
Speed still matters (bi-weekly payouts), so 10/20-day pass is shown too.

Strategies evaluated: 52pPlus (best build) and the FairPrice user_spec (recent).
Run: python3 goat_eval.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3"), ("..", "newstrat"),
            ("..", "FairPriceStrategy")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
sys.path.insert(0, HERE)
import data, strategies as S, engine, ftmo               # noqa: E402
from search import build_days                             # noqa: E402

NP = 120_000
TARGET = 1.03; DAILY = 0.03                                # +3% target, 3% daily
STATIC_FLOOR = 0.95                                        # 5% static max loss
TRAIL = 0.05                                               # 5% trailing max loss
RISKS = (0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02)
FEE_AUD = 100.0
ftmo.MIN_DAYS = 0                                          # Blitz: no minimum trading days


def get_trades():
    import ChallengePhase52pPlus as P
    tr52, ad52 = P.trades()
    d52 = build_days(tr52, ad52, P.BREAKER)

    import user_spec as U
    df = S.prep(data.load()); adf = np.array(sorted(df["date"].unique()))
    trf = U.build(df, U.CFG["cost_pts"])
    df_ = build_days(trf, adf, 0.0)                        # seq() already caps the day at 3 losses
    return {"52pPlus": (d52, engine.edge_stats(tr52)),
            "FairPrice user_spec": (df_, engine.edge_stats(trf))}


def best(days, dl, floor=STATIC_FLOOR, trail=0.0):
    br = (-1, None, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, dl, n_paths=NP, seed=11, block=5, floor=floor, daily=DAILY,
                        target=TARGET, consistency=False, trail_dd=trail)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def main():
    strat = get_trades()
    print("=" * 84)
    print("GOAT FUNDED 'Blitz' 10k — 1-step, +3% target, 3% daily, 5% max loss, no time/consistency")
    print("=" * 84)
    for name, (days, es) in strat.items():
        print(f"\n### {name}   (edge WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f})")
        for mode, floor, trail in [("5% STATIC ", STATIC_FLOOR, 0.0), ("5% TRAILING", 0.90, TRAIL)]:
            pe, re, me = best(days, 250, floor, trail)          # eventual (no time limit)
            p20, r20, m20 = best(days, 20, floor, trail)
            p10, r10, m10 = best(days, 10, floor, trail)
            md = me["mean_days_to_pass"]
            print(f"  [{mode}]  EVENTUAL {pe*100:4.1f}% pass / {me['blow_rate']*100:4.1f}% blow "
                  f"(r*={re*100:.2f}%, ~{md:.0f}d avg)   |  20d {p20*100:4.1f}%  10d {p10*100:4.1f}%")
    print("\n" + "-" * 84)
    print("Benchmarks: 0EV eventual ceiling (static) = 5/(3+5) = 62.5%.  FTMO 1-step 15k ~ 55-58% @2mo.")
    print("Cost per funded 10k (static, eventual) = $100 AUD / eventual-pass-rate:")
    for name, (days, es) in strat.items():
        pe, re, me = best(days, 250, STATIC_FLOOR, 0.0)
        print(f"  {name:22} {FEE_AUD/max(pe,1e-9):6.0f} AUD/funded  (first account $84 -> {84/max(pe,1e-9):.0f})")


if __name__ == "__main__":
    main()
