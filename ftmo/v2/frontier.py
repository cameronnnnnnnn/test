"""
frontier.py — capstone analysis on the BEST strategy found
(US opening-range breakout, 16:00 server, 15-min range, 50pt stop, trail 3R,
 volume-confirmed). Produces:
  1. Robustness: in-sample vs out-of-sample, long vs short, cost stress
  2. The pass%/blow% frontier across deadlines x risk (where is 80%?)
  3. Theoretical proof: daily Sharpe required for 80%-in-3-weeks vs achievable
"""
import numpy as np, pandas as pd
import data, strategies, engine, ftmo
from run import build_days

BEST = dict(open_min=16*60, or_min=15, stop_pts=50, tp_R=0.0, be_R=0.0,
            trail_R=3.0, vol_filter=True)

def backtest(df, params, cost=2.0):
    orders = strategies.orb(df, **params)
    return engine.simulate(df, orders, cost_pts=cost)

def robustness(df, all_dates):
    print("\n### ROBUSTNESS — best strategy")
    tr = backtest(df, BEST)
    es = engine.edge_stats(tr)
    print(f"  full sample : n={es['n']} WR={es['wr']*100:.1f}% expR={es['expR']:+.3f} PF={es['pf']:.2f}")
    # in-sample (first 2/3) vs OOS (last 1/3) by date
    cut = all_dates[int(len(all_dates)*0.67)]
    ins = tr[tr["entry_dt"] < cut]; oos = tr[tr["entry_dt"] >= cut]
    print(f"  in-sample   : n={len(ins)} expR={ins['R'].mean():+.3f}  ({pd.Timestamp(all_dates[0]).date()}..{pd.Timestamp(cut).date()})")
    print(f"  OUT-OF-SAMPLE: n={len(oos)} expR={oos['R'].mean():+.3f}  ({pd.Timestamp(cut).date()}..{pd.Timestamp(all_dates[-1]).date()})")
    lo = tr[tr["dir"] == 1]; sh = tr[tr["dir"] == -1]
    print(f"  long  : n={len(lo)} expR={lo['R'].mean():+.3f} WR={(lo['R']>0).mean()*100:.1f}%")
    print(f"  short : n={len(sh)} expR={sh['R'].mean():+.3f} WR={(sh['R']>0).mean()*100:.1f}%")
    for c in [2.0, 4.0, 6.0]:
        e = engine.edge_stats(backtest(df, BEST, cost=c))
        print(f"  cost {c:.0f}pt : expR={e['expR']:+.3f} PF={e['pf']:.2f}")

def frontier(df, all_dates):
    print("\n### FRONTIER — pass% (blow%) by deadline x risk   [best strategy]")
    tr = backtest(df, BEST)
    days = build_days(tr, all_dates)
    risks = [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025]
    deads = [("1wk",5),("2wk",10),("3wk",15),("4wk",20),("6wk",30),("8wk",40),("12wk",60)]
    hdr = "  deadline | " + " ".join(f"r={r*100:>4.2f}%" for r in risks)
    print(hdr); print("  " + "-"*(len(hdr)-2))
    best_by_dead = {}
    for nm, T in deads:
        cells = []; best = (0,0,0)
        for r in risks:
            m = ftmo.run_mc(days, r, T, n_paths=30000, seed=11)
            cells.append(f"{m['pass_rate']*100:4.0f}/{m['blow_rate']*100:>2.0f}")
            if m["pass_rate"] > best[0]:
                best = (m["pass_rate"], m["blow_rate"], r)
        best_by_dead[nm] = best
        print(f"  {nm:>7} | " + "  ".join(cells))
    print("\n  best pass% per deadline (pass / blow / risk):")
    for nm,_ in deads:
        p,b,r = best_by_dead[nm]
        flag = "  <-- crosses 80%!" if p>=0.80 else ""
        print(f"    {nm:>5}: {p*100:4.1f}% / {b*100:4.1f}% / r={r*100:.2f}%{flag}")
    return days

def daily_sharpe_proof(df, all_dates, days):
    print("\n### THEORETICAL — what 80%-in-3-weeks actually requires")
    # empirical daily return distribution of the best strategy at its best 3wk risk
    r = 0.02
    dR = np.asarray(days["day_R"], float)
    daily_ret = dR * r                       # fraction of balance per day
    mu, sd = daily_ret.mean(), daily_ret.std()
    print(f"  best strategy @ r={r*100:.0f}%: daily mean={mu*100:+.3f}%  std={sd*100:.3f}%  "
          f"=> daily Sharpe={mu/sd:.3f} (annualized ~{mu/sd*np.sqrt(252):.1f})")
    # normal-day model: pass% at 15 days vs daily Sharpe
    def normpass(mu_d, sd_d, T=15, N=40000, seed=3):
        rng = np.random.default_rng(seed)
        R = rng.normal(mu_d, sd_d, size=(N,T))
        E = np.ones(N); alive=np.ones(N,bool); passed=np.zeros(N,bool); dtr=np.zeros(N,int)
        for t in range(T):
            day = R[:,t]
            low = np.minimum(day,0)                 # approx intraday low ~ close if down
            alive &= ~((low <= -0.03) | (E*(1+low) <= 0.90))
            E = np.where(alive&~passed, E*(1+day), E); dtr += (alive&~passed).astype(int)
            passed |= alive & (E>=1.10) & (dtr>=4)
        return passed.mean()
    print("  normal-day model, +10% target / -10% floor / -3% daily, 15 trading days:")
    print("   daily Sharpe -> 15-day pass%")
    for s in [0.05,0.10,0.15,0.20,0.30,0.50,0.75,1.0,1.25]:
        # fix sd at the strategy's sd, set mu = s*sd
        p = normpass(s*sd, sd)
        mark = "  <-- 80%" if p>=0.80 else ("  <-- ~ach." if abs(s-mu/sd)<0.03 else "")
        print(f"     {s:>4.2f}  ->  {p*100:4.1f}%{mark}")

def main():
    df = strategies.prep(data.load())
    all_dates = np.array(sorted(df["date"].unique()))
    print("="*100)
    print("CAPSTONE: best NAS100 strategy vs the >80%-in-<3-weeks target")
    print("Best = US ORB 16:00 server, 15m range, 50pt stop, trail 3R, volume-confirmed")
    print("="*100)
    robustness(df, all_dates)
    days = frontier(df, all_dates)
    daily_sharpe_proof(df, all_dates, days)

if __name__ == "__main__":
    main()
