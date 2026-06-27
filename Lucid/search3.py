"""
Lucid/search3.py — round 3: fine-tune the ORB winner (OR length / stop / risk) and
check COST sensitivity. Report MONTHLY (21d) and EVENTUAL (63d, ~no time limit) pass.

Run: python3 search3.py
"""
import numpy as np, pandas as pd
import data, strategies as S, engine, lucid

NP = 50000

def stats(days, rd):
    m21 = lucid.run_eval_mc(days, rd, 21, n_paths=NP, seed=7, breach="eod")
    m63 = lucid.run_eval_mc(days, rd, 63, n_paths=NP, seed=7, breach="eod")
    return m21, m63

def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique()))
    print(f"loaded {len(df):,} bars, {len(ad)} weekdays. EOD breach. {NP} paths.")
    print("="*112)

    # --- COST sensitivity on the base winner ---
    print("COST sensitivity (ORB o960 30m s60 tp3, risk $200):")
    for cost in [0.5, 0.75, 1.0, 1.5]:
        tr = engine.simulate(df, S.orb(df, open_min=960, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True), cost_pts=cost)
        es = engine.edge_stats(tr); days = lucid.build_days(tr, ad)
        m21, m63 = stats(days, 200)
        print(f"  cost {cost:4.2f}pt: expR={es['expR']:+.3f}  monthly={m21['pass_rate']*100:4.1f}%  "
              f"eventual={m63['pass_rate']*100:4.1f}%  blow(ev)={m63['blow_rate']*100:4.1f}%")
    print("-"*112)

    COST = 1.0   # conservative realistic NQ-micro round-turn
    # --- fine param + risk grid ---
    print(f"FINE TUNE at COST={COST}pt  (monthly / eventual pass, best risk in [180..260]):")
    print(f"  {'config':26s} {'expR':>7} {'WR':>5} | {'risk$':>6} {'MONTHLY':>8} {'EVENT':>7} {'blow_ev':>8} {'med':>5}")
    best = None
    for orm in [25, 30, 35, 40]:
        for stop in [55, 60, 65, 70]:
            for tp in [3.0, 3.5]:
                orders = S.orb(df, open_min=960, or_min=orm, stop_pts=stop, tp_R=tp, be_R=1.0, vol_filter=True)
                tr = engine.simulate(df, orders, cost_pts=COST)
                if len(tr) < 100: continue
                es = engine.edge_stats(tr); days = lucid.build_days(tr, ad)
                # pick risk by monthly pass, but require size <= 20 micros
                brisk = None
                for rd in [180, 200, 220, 240, 260]:
                    if lucid.micros_for(rd, stop) > 20+1e-9: continue
                    m = lucid.run_eval_mc(days, rd, 21, n_paths=NP, seed=7, breach="eod")
                    if brisk is None or m["pass_rate"] > brisk[1]["pass_rate"]:
                        brisk = (rd, m)
                rd, m21 = brisk
                m63 = lucid.run_eval_mc(days, rd, 63, n_paths=NP, seed=7, breach="eod")
                name = f"ORB 30o960 {orm}m s{stop} tp{tp}"
                row = dict(name=name, expR=es["expR"], wr=es["wr"], risk=rd,
                           p21=m21["pass_rate"], p63=m63["pass_rate"], blow=m63["blow_rate"], med=m21["med_days"])
                if best is None or row["p21"] > best["p21"]: best = row
                print(f"  {name:26s} {es['expR']:+.3f} {es['wr']*100:4.1f}% | ${rd:<5.0f} "
                      f"{m21['pass_rate']*100:6.1f}%  {m63['pass_rate']*100:5.1f}%  {m63['blow_rate']*100:6.1f}%  {m21['med_days']:.0f}d")
    print("="*112)
    print(f"BEST monthly: {best['name']}  risk ${best['risk']:.0f}  "
          f"MONTHLY={best['p21']*100:.1f}%  EVENTUAL={best['p63']*100:.1f}%  blow={best['blow']*100:.1f}%  med={best['med']:.0f}d")

if __name__ == "__main__":
    main()
