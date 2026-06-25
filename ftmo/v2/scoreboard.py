"""
scoreboard.py — the definitive battery. One representative (best) config per
strategy family, scored on WR / expR / 3-week & 4-week(monthly) pass% & blow%.
This is the table that answers the user's loop. Run: python3 scoreboard.py
"""
import numpy as np, pandas as pd
import data, strategies, engine, ftmo
from run import build_days, RISKS, WK3, WK4, COST

def score_orders(orders, df, all_dates, fix_risk=None):
    trades = engine.simulate(df, orders, cost_pts=COST)
    if not len(trades):
        return None
    es = engine.edge_stats(trades)
    days = build_days(trades, all_dates)
    tpw = es["n"] / (len(all_dates) / 5.0)
    risks = [fix_risk] if fix_risk else RISKS
    best = None
    for r in risks:
        m = ftmo.run_mc(days, r, WK3, n_paths=25000, seed=7)
        if best is None or m["pass_rate"] > best[1]["pass_rate"]:
            best = (r, m)
    r3, m3 = best
    m4 = ftmo.run_mc(days, r3, WK4, n_paths=25000, seed=7)
    return dict(n=es["n"], tpw=tpw, wr=es["wr"], expR=es["expR"], pf=es["pf"],
                maxR=es["maxR"], r=r3, pass3=m3["pass_rate"], blow3=m3["blow_rate"],
                pass4=m4["pass_rate"], blow4=m4["blow_rate"])

def main():
    df = strategies.prep(data.load())
    ad = np.array(sorted(df["date"].unique()))
    S = strategies
    O = lambda **k: S.orb(df, **k)
    base = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0, trail_R=3.0)

    battery = [
        # name, orders
        ("MeanRev: VWAP-fade k2.5",     S.vwap_fade(df, k=2.5, stop_pts=50, tp_R=1.0)),
        ("MeanRev: OR-fade tp1.5",      S.or_fade(df, or_min=30, poke_pts=15, stop_pts=40, tp_R=1.5)),
        ("Breakout: ORB hard-TP3+BE",   O(**{**base, "tp_R":3.0, "be_R":1.0, "trail_R":0.0})),
        ("Breakout: ORB trail2R",       O(**{**base, "trail_R":2.0})),
        ("Breakout: London ORB",        O(**{**base, "open_min":10*60})),
        ("Breakout: ORB retest",        S.orb_retest(df, open_min=16*60, or_min=15, stop_pts=50, trail_R=3.0)),
        ("Breakout: ORB long-only",     O(**{**base, "long_only":True})),
        ("** BEST: vol US ORB trail3",  O(**{**base, "vol_filter":True})),
        ("Combo: US16:00 + US16:30",    S.orb(df, **base) + S.orb(df, **{**base, "open_min":16*60+30})),
        ("Combo: US16 + London10",      S.orb(df, **base) + S.orb(df, **{**base, "open_min":10*60})),
    ]
    print("="*128)
    print(f"{'STRATEGY':30s} {'n':>4} {'t/wk':>4} {'WR':>5} {'expR':>7} {'PF':>5} "
          f"{'r*':>5} | {'3wk pass':>8} {'blow':>5} | {'4wk pass':>8} {'blow':>5}")
    print("="*128)
    rows = []
    for name, orders in battery:
        s = score_orders(orders, df, ad)
        if not s:
            print(f"{name:30s}  -- no trades"); continue
        rows.append((name, s))
        print(f"{name:30s} {s['n']:>4} {s['tpw']:>4.1f} {s['wr']*100:>4.1f}% "
              f"{s['expR']:>+6.3f} {s['pf']:>5.2f} {s['r']*100:>4.2f}% | "
              f"{s['pass3']*100:>7.1f}% {s['blow3']*100:>4.1f}% | "
              f"{s['pass4']*100:>7.1f}% {s['blow4']*100:>4.1f}%")
    print("="*128)
    best = max(rows, key=lambda x: x[1]["pass3"])
    print(f"Best 3-week pass: {best[0].strip('* ')}  ->  {best[1]['pass3']*100:.1f}% "
          f"(blow {best[1]['blow3']*100:.1f}%) at r={best[1]['r']*100:.2f}%")
    print(f"TARGET was >80% in <3 weeks.  Gap: best is {best[1]['pass3']*100:.0f}%, "
          f"i.e. {0.80/best[1]['pass3']:.1f}x short of the bar.")

if __name__ == "__main__":
    main()
