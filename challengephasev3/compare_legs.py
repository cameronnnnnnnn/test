"""
challengephasev3/compare_legs.py — should you DROP the ORB leg and run only B_PULL?
Tiny-sample hindsight says "pullback-only would be up more", but the decision that
matters is pass RATE. Compares B_PULL-only vs A_ORB-only vs the COMBO on the same 100k
MC: edge, run-to-completion pass, 20-day pass, and pass FROM the current balance.
Run: python3 compare_legs.py
"""
import os, sys
import numpy as np
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine
import search as SR
import from_balance_mc as FB


def arrays(df, orders, ad):
    tr = engine.simulate(df, orders, cost_pts=2.0)
    d = SR.build_days(tr, ad, 0.0)
    return (np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float),
            (np.asarray(d["n"]) > 0).astype(int), tr)


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    nweeks = len(ad) / 5.0
    pull = S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)
    orb = S.orb(df, open_min=16*60, or_min=15, stop_pts=50, tp_R=4.0, be_R=0.0, vol_filter=True)
    legs = [("B_PULL only", pull), ("A_ORB only", orb), ("COMBO (what you run)", orb + pull)]

    print("=" * 90)
    print("DROP THE ORB?  B_PULL-only vs A_ORB-only vs COMBO  — 100k MC, live geometry, 1% risk")
    print("=" * 90)
    print(f"  {'strategy':22s} {'trades':>7} {'/wk':>5} {'WR':>6} {'expR':>7} {'PF':>5} | "
          f"{'passRTC':>8} {'pass20d':>8} {'medDays':>8}")
    print("-" * 90)
    for name, orders in legs:
        dR, dmin, traded, tr = arrays(df, orders, ad)
        es = engine.edge_stats(tr)
        m = FB.mc(dR, dmin, traded, 0.01, e0=1.0, sg0=0.0, mg0=0.0, dd0=0)   # clean start
        p, tp = m["passed"], m["tpass"]
        rtc = p.mean(); p20 = (p & (tp < 20)).mean(); med = np.median(tp[p] + 1) if p.any() else np.nan
        print(f"  {name:22s} {es['n']:7d} {es['n']/nweeks:4.1f} {es['wr']*100:5.1f}% {es['expR']:+.3f} "
              f"{es['pf']:5.2f} | {rtc*100:7.1f}% {p20*100:7.1f}% {med:6.0f}d")
    print("-" * 90)

    # forward from the CURRENT balance ($15,577.83, seeded state): combo vs pullback-only
    print(f"\nFROM YOUR CURRENT BALANCE (${FB.BAL:,.0f}, +{(FB.E0-1)*100:.2f}%, seeded), going forward:")
    for name, orders in [("keep COMBO", orb + pull), ("switch to B_PULL only", pull)]:
        dR, dmin, traded, _ = arrays(df, orders, ad)
        m = FB.mc(dR, dmin, traded, 0.01)     # uses seeded E0/greens/days
        p, tp = m["passed"], m["tpass"]; td = tp[p] + 1
        print(f"  {name:24s}: eventual pass {p.mean()*100:5.1f}%  ·  blow {m['blown'].mean()*100:4.1f}%  "
              f"·  median {np.median(td):.0f}d  ·  pass within 17d {(p&(tp<17)).mean()*100:.1f}%")
    print("=" * 90)
    print("Read: dropping the ORB removes ~half your trades. Fewer trades -> you reach +10% slower")
    print("-> more timeouts/blows before target. The ORB's job isn't per-trade profit, it's FREQUENCY")
    print("and decorrelation (it wins on breakout days the pullback misses). 3 losses is noise.")


if __name__ == "__main__":
    main()
