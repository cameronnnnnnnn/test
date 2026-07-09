"""
challengephaseHF/topstep_eval.py — 52p under the TopStep 50k Trading Combine rules:
  account 50,000 · profit target $3,000 (6%) · Max Loss Limit $2,000 (4%, ONE rule = no daily
  limit) · 50% consistency · max size 5 mini / 50 micro NQ ($100/pt).

Max Loss Limit (confirmed): EOD trailing — floor = (account balance high) - $2,000, set at the
end of each day, and it STOPS trailing once it reaches the starting balance (once you're up $2k,
your floor locks at $50k breakeven). That lock makes the endgame much safer, so we model it, and
also show the harsher no-lock case for reference. Run: python3 topstep_eval.py
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
ACCT = 50000.0; TARGET = 1.06; DD = 0.04             # +6% target ($3k), 4% trailing max loss ($2k)
RISKS = (0.003, 0.004, 0.005, 0.0075, 0.01, 0.0125)
MNQ_PER_POINT = 2.0; AVG_STOP_PTS = 50


def best(days, deadline, **kw):
    br = (-1, None, None)
    for r in RISKS:
        m = ftmo.run_mc(days, r, deadline, n_paths=NP, seed=11, block=5,
                        daily=0.0, target=TARGET, consistency=True, trail_dd=DD, **kw)
        if m["pass_rate"] > br[0]: br = (m["pass_rate"], r, m)
    return br


def micros(r):
    return (r * ACCT) / (AVG_STOP_PTS * MNQ_PER_POINT)


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = engine.simulate(df, CP52.build(df), cost_pts=CP52.COST)
    days = build_days(tr[tr["day"].isin(set(ad))], ad, CP52.BREAKER)

    print("=" * 86)
    print("52p under TOPSTEP 50k COMBINE — 50k · +$3,000 (6%) · $2,000 (4%) EOD-trailing · no daily · 50% cons")
    print("=" * 86)
    print(f"  {'drawdown model':30} {'risk*':>6} {'~micros/leg':>12} {'PASS':>6} {'BLOW':>6} {'still':>6}")
    for tag, kw in [("EOD-trailing, LOCK at start (TopStep)", dict(trail_lock=True)),
                    ("EOD-trailing, no lock (harsher ref)",   dict(trail_lock=False))]:
        for dl in (20, 60):
            p, r, m = best(days, dl, **kw)
            print(f"  {tag+f'  {dl}d':30} {r*100:5.2f}% {micros(r):11.1f} {p*100:5.1f}% "
                  f"{m['blow_rate']*100:5.1f}% {m['timeout_rate']*100:5.1f}%")
        print()

    print("-" * 86)
    print("FTMO 15k reference: ~55% in 20 days at 0.75%. Cap 50 micros=$100/pt; a leg is ~2-3 micros,")
    print("4 legs ~8-12 -> well under cap. The $2k (4%) trailing is the real constraint -> tiny sizing.")
    print("\nSTILL two hard blockers to actually RUN it (same as any futures firm):")
    print("  1. Platform: TopStep = TopstepX/Tradovate/NinjaTrader/Rithmic, NOT MetaTrader. The .mq5")
    print("     EA cannot run there — the strategy has to be ported (e.g. NinjaScript C#).")
    print("  2. Netting, not hedging: futures net, but 52p runs 4 independent long/short legs at once")
    print("     -> they'd cancel; needs a single-net-position rewrite. Intraday-trailing (if TopStep")
    print("     ever measures the high intraday, not EOD) would be harder than these EOD numbers.")


if __name__ == "__main__":
    main()
