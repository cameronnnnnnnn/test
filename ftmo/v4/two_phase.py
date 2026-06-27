"""
v4/two_phase.py — two-phase FUNDED strategy:
  Phase 1 (FAST): aggressive risk r1, withdraw ALL profit each day, until cumulative
    withdrawals reach the break-even target B (~2.5%). Goal: bank break-even fast so
    the rest is house money.
  Phase 2 (SAFE): low risk r2, withdraw above a profit buffer, grind for lifetime
    extraction with low blow-up.
Same FTMO funded rules (static 10% floor, 3% daily). Same bug-fixed 4R combo edge.
Measures: P(reach break-even), days-to-break-even, P(blow BEFORE break-even),
avg total lifetime extraction — vs the single-phase baseline.
"""
import numpy as np, strategies as S, engine, data
from run import build_days
FLOOR = 0.90; DAILY = 0.03; MONTH = 21

def combo_days(df, ad, tp=4.0):
    o = S.orb(df, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
              tp_R=tp, be_R=0.0, trail_R=0.0) + S.vwap_pullback(df, stop_pts=40, tp_R=tp, trail_R=0.0)
    d = build_days(engine.simulate(df, o, cost_pts=2.0), ad)
    return np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float)

def _paths(dR, dmin, months, N, block, seed):
    rng = np.random.default_rng(seed); nD = len(dR); H = months*MONTH
    nb = int(np.ceil(H/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:H]
    return dR[idx], dmin[idx], H

def _result(reached, alive, t_be, cum):
    blow_pre = (~alive) & ~reached
    return dict(reach_be=reached.mean()*100, blow_pre_be=blow_pre.mean()*100,
                med_days_be=np.median(t_be[reached]) if reached.any() else np.nan,
                avg_life_wd=cum.mean()*100, med_life_wd=np.median(cum)*100)

def two_phase(dR, dmin, r1, r2, B=0.025, buffer=0.10, months=60, N=40000, block=5, seed=0):
    R_, Rmin, H = _paths(dR, dmin, months, N, block, seed)
    E = np.ones(N); alive = np.ones(N, bool); cum = np.zeros(N)
    reached = np.zeros(N, bool); t_be = np.full(N, -1)
    for t in range(H):
        p1 = cum < B                                   # still racing to break-even
        r = np.where(p1, r1, r2)
        dead = alive & (((Rmin[:,t]*r) <= -DAILY) | (E*(1+Rmin[:,t]*r) <= FLOOR))
        alive &= ~dead
        E = np.where(alive, E*(1+R_[:,t]*r), E)
        # phase-1 paths: withdraw ALL profit daily (race); phase-2 paths: monthly buffer
        d1 = alive & p1 & (E > 1.0)
        take = np.where(d1, E-1.0, 0.0); cum += take; E -= take
        just = alive & p1 & (cum >= B) & ~reached
        reached |= just; t_be = np.where(just & (t_be<0), t, t_be)
        if (t+1) % MONTH == 0:
            d2 = alive & ~p1 & (E > 1.0+buffer)
            take2 = np.where(d2, E-(1.0+buffer), 0.0); cum += take2; E -= take2
    return _result(reached, alive, t_be, cum)

def single(dR, dmin, r, B=0.025, buffer=0.10, months=60, N=40000, block=5, seed=0):
    """constant risk, monthly withdraw above buffer from the start (true baseline)."""
    R_, Rmin, H = _paths(dR, dmin, months, N, block, seed)
    E = np.ones(N); alive = np.ones(N, bool); cum = np.zeros(N)
    reached = np.zeros(N, bool); t_be = np.full(N, -1)
    for t in range(H):
        dead = alive & (((Rmin[:,t]*r) <= -DAILY) | (E*(1+Rmin[:,t]*r) <= FLOOR))
        alive &= ~dead
        E = np.where(alive, E*(1+R_[:,t]*r), E)
        if (t+1) % MONTH == 0:
            d = alive & (E > 1.0+buffer)
            take = np.where(d, E-(1.0+buffer), 0.0); cum += take; E -= take
        just = alive & (cum >= B) & ~reached
        reached |= just; t_be = np.where(just & (t_be<0), t, t_be)
    return _result(reached, alive, t_be, cum)

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    dR, dmin = combo_days(df, ad)
    print("FUNDED two-phase (fast to break-even, then safe). Break-even B=2.5%. 4R combo.")
    print(f"  {'config':30s} {'reachBE%':>8} {'blowPreBE%':>10} {'daysBE':>7} {'avgLifeWd%':>10} {'medWd%':>7}")
    FUND = 2.45*135                                  # ~$331 to fund (2.45 challenges)
    rows = [
        ("SINGLE r=0.40% buf10%",  single(dR,dmin,0.004,buffer=0.10)),
        ("2-PHASE r1=0.6->r2=0.4%", two_phase(dR,dmin,0.006,0.004)),
        ("2-PHASE r1=0.75->r2=0.4%",two_phase(dR,dmin,0.0075,0.004)),
        ("2-PHASE r1=1.0->r2=0.4%", two_phase(dR,dmin,0.010,0.004)),
    ]
    for name, m in rows:
        net = m['avg_life_wd']/100*15000*0.9 - FUND
        print(f"  {name:30s} {m['reach_be']:7.1f} {m['blow_pre_be']:9.1f} "
              f"{m['med_days_be']:6.0f} {m['avg_life_wd']:9.1f} {m['med_life_wd']:6.1f}  net ${net:+.0f}")
    print("\n reachBE%=accounts that bank break-even; blowPreBE%=lost before break-even (net -fee);")
    print(" daysBE=median trading days to break-even; avgLifeWd%/medWd%=total lifetime extraction;")
    print(" net $=avg payout (90% of extraction x $15k) minus ~$331 funding cost, per funded account.")

if __name__ == "__main__":
    main()
