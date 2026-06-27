"""
Lucid/confirm.py — lock the winner at REAL (integer-micro) position sizes, report
monthly + eventual pass, and the buy-N-accounts EV. Micros are $2/pt, so at stop S a
1-micro stop-out risks S*2 dollars; size must be an integer number of micros (<=20).

Run: python3 confirm.py
"""
import numpy as np
import data, strategies as S, engine, lucid

COST = 1.0; NP = 80000
FEE = 70.0; RESET = 60.0

def micro_risk(stop, n): return stop * lucid.PT_MICRO * n   # $ risked per stop-out

def report(name, orders, stop, sizes):
    tr = engine.simulate(DF, orders, cost_pts=COST)
    es = engine.edge_stats(tr); days = lucid.build_days(tr, AD)
    print(f"\n{name}:  n={es['n']}  WR={es['wr']*100:.1f}%  expR={es['expR']:+.3f}  ({es['n']/ (len(AD)/5):.1f} trades/wk)")
    print(f"  {'size':>10} {'risk$':>6} {'MONTHLY':>8} {'2-mo':>6} {'EVENT':>7} {'blow_ev':>8} {'med':>5}")
    best = None
    for n in sizes:
        rd = micro_risk(stop, n)
        m21 = lucid.run_eval_mc(days, rd, 21, n_paths=NP, seed=11, breach="eod")
        m42 = lucid.run_eval_mc(days, rd, 42, n_paths=NP, seed=11, breach="eod")
        m63 = lucid.run_eval_mc(days, rd, 63, n_paths=NP, seed=11, breach="eod")
        print(f"  {n:2d} micros  ${rd:5.0f} {m21['pass_rate']*100:7.1f}% {m42['pass_rate']*100:5.1f}% "
              f"{m63['pass_rate']*100:6.1f}% {m63['blow_rate']*100:7.1f}% {m21['med_days']:.0f}d")
        if best is None or m21["pass_rate"] > best[1]: best = (n, m21["pass_rate"], m63["pass_rate"], m63["blow_rate"])
    return best

def main():
    global DF, AD
    DF = S.prep(data.load()); AD = np.array(sorted(DF["date"].unique()))
    print("="*92)
    print("LUCID 25K FLEX EVAL — winner at real integer-micro sizes (EOD trailing DD, EOD breach)")
    print(f"$25k, +$1,250 target, $1,000 EOD-trailing DD, no daily limit, 50% consistency. COST={COST}pt")
    print("="*92)

    b1 = report("ORB 16:00 30m  s60 tp3 (THE WINNER)",
                S.orb(DF, open_min=960, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True),
                60, [1,2,3,4])
    b2 = report("ORB 16:00 30m  s55 tp3 (2 micros = $220 exact)",
                S.orb(DF, open_min=960, or_min=30, stop_pts=55, tp_R=3.0, be_R=1.0, vol_filter=True),
                55, [1,2,3,4])
    b3 = report("ORB 16:00 30m  s50 tp3 (2 micros = $200 exact)",
                S.orb(DF, open_min=960, or_min=30, stop_pts=50, tp_R=3.0, be_R=1.0, vol_filter=True),
                50, [2,3,4])

    # --- EV of the deployable pick (use the winner @ 2 micros) ---
    n, p21, p63, blow = b1
    print("\n" + "="*92)
    print(f"DEPLOYABLE PICK: ORB 16:00 30m s60 tp3, {n} micros ($ {micro_risk(60,n):.0f} risk/trade)")
    print("="*92)
    print(f"  monthly pass {p21*100:.1f}%   eventual pass {p63*100:.1f}%   eventual blow {blow*100:.1f}%")
    # cost to get one funded acct: pay $70 first try, $60 each reset, until a pass
    exp_attempts = 1.0/p63
    cost_to_fund = FEE + (exp_attempts-1.0)*RESET
    print(f"  eventual pass {p63*100:.1f}% -> ~{exp_attempts:.2f} attempts to a funded acct")
    print(f"  expected cost to get funded = $70 + {exp_attempts-1:.2f}*$60 = ${cost_to_fund:.0f}")
    print(f"  (vs a $25k funded account — strongly convex if the funded phase pays out)")

if __name__ == "__main__":
    main()
