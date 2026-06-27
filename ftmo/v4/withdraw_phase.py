"""
v4/withdraw_phase.py — FUNDED phase modeled the video's way: maximise total
WITHDRAWALS (money extracted before the account dies), not pass rate.

Reproduces the heatmap axes on NAS100 under FTMO funded rules (static 10% floor,
3% DAILY cap — the video's Topstep has NO 3% daily cap, so we test whether the
'low-R:R + dd_frac' pattern survives it):
  R:R (take-profit as a fraction/multiple of the 1R stop): 0.33,0.5,1,2,3,4
  Risk geometry: frac_1pct / frac_2pct (fixed) ; dd_frac_k (risk k*(equity-floor)) ;
  Withdraw profit above the initial balance each month; floor stays at 90% of initial.
"""
import numpy as np, strategies as S, engine, data
from run import build_days

FLOOR = 0.90; DAILY = 0.03; MONTH = 21
COST = 2.0

def days_for(df, ad, tp):
    o = S.orb(df, open_min=16*60, or_min=15, stop_pts=50, vol_filter=True,
              tp_R=tp, be_R=0.0, trail_R=0.0) + S.vwap_pullback(df, stop_pts=40, tp_R=tp, trail_R=0.0)
    tr = engine.simulate(df, o, cost_pts=COST)
    d = build_days(tr, ad)
    return np.asarray(d["day_R"], float), np.asarray(d["day_min_R"], float), engine.edge_stats(tr)

def withdraw_mc(dR, dmin, sizing, months=12, N=20000, block=5, seed=0, rmax=0.02, buffer=0.0):
    """sizing=('fixed',r) or ('dd',k). buffer=keep this cushion above initial before
    withdrawing. Returns avg total withdrawals (% of initial) and survival rate."""
    rng = np.random.default_rng(seed); nD = len(dR); H = months*MONTH
    nb = int(np.ceil(H/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:H]
    R_, Rmin = dR[idx], dmin[idx]
    E = np.ones(N); alive = np.ones(N, bool); wd = np.zeros(N)
    for t in range(H):
        rt = R_[:,t]; rmin = Rmin[:,t]
        if sizing[0]=="fixed":
            rr = np.full(N, sizing[1])
        else:                                   # dd_frac: risk k*(equity-floor)/equity
            rr = np.clip(sizing[1]*(E-FLOOR)/np.maximum(E,1e-9), 0.001, rmax)
        daily_breach = (rmin*rr) <= -DAILY
        floor_breach = E*(1+rmin*rr) <= FLOOR
        dead = alive & (daily_breach | floor_breach)
        alive &= ~dead
        E = np.where(alive, E*(1+rt*rr), E)
        if (t+1) % MONTH == 0:                  # monthly payout: take profit above buffer
            take = np.where(alive & (E>1.0+buffer), E-(1.0+buffer), 0.0)
            wd += take; E = E - take
    return wd.mean()*100, alive.mean()*100

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    RRs = [0.33, 0.5, 1.0, 2.0, 3.0, 4.0]
    geoms = [("frac_1pct",("fixed",0.01)), ("frac_2pct",("fixed",0.02)),
             ("dd_frac_10",("dd",0.10)), ("dd_frac_15",("dd",0.15))]
    print("AVG WITHDRAWALS (% of initial, 12 months) — R:R x risk geometry, NAS/FTMO funded")
    print("  (FTMO 3% daily cap enforced; rmax cap 2% so 1 trade can't breach it)")
    hdr = "  R:R   " + "".join(f"{g[0]:>12}" for g in geoms) + "   WR/expR"
    print(hdr); print("  "+"-"*(len(hdr)-2))
    for tp in RRs:
        dR, dmin, es = days_for(df, ad, tp)
        cells=[]
        for _, sz in geoms:
            w, surv = withdraw_mc(dR, dmin, sz)
            cells.append(f"{w:6.1f}({surv:2.0f}%)")
        print(f"  {tp:>4}R " + "".join(f"{c:>12}" for c in cells) + f"   {es['wr']*100:.0f}%/{es['expR']:+.3f}")
    print("\n  cell = avg cumulative withdrawal % (survival% over 12mo). Compare the R:R rows.")

    print("\n" + "="*78)
    print("LIFETIME EXTRACTION per funded account (run to death) — the video's metric")
    print("  (video: $8900/$50k = 17.8% lifetime avg). NAS/FTMO 4R combo:")
    print("="*78)
    dR, dmin, _ = days_for(df, ad, 4.0)
    print("  r      buffer   avg%   median%   avg_life(mo)")
    best = None
    for r in [0.004, 0.005, 0.0075]:
        for buf in [0.0, 0.05, 0.10, 0.15]:
            a, med, life, s = lifetime(dR, dmin, r, buf)
            print(f"  {r*100:.2f}%   {buf*100:2.0f}%    {a:5.1f}   {med:5.1f}     {life:5.1f}")
            if best is None or a > best[0]: best = (a, r, buf)
    avg = best[0]
    print(f"\n  Best avg lifetime extraction: {avg:.0f}% at r={best[1]*100:.2f}%, buffer={best[2]*100:.0f}%.")
    print( "  YOUR PLAN EV (FTMO $15k, 90/10 split, ~2.45 challenges @ $135 to fund):")
    fee = 2.45*135; payout = avg/100 * 15000 * 0.9
    print(f"    cost to fund ~${fee:.0f} ; avg payout/funded ~${payout:.0f} (you keep 90%)")
    print(f"    NET ~${payout-fee:.0f} per funded account. Break-even is ~2.45% extraction;")
    print(f"    avg extraction ~{avg:.0f}% -> strongly net +EV. (avg is right-skewed: median lower.)")
    print(" NOTE: heatmap geometry (0.5R + dd_frac) does NOT transfer (NAS tight-TP is -EV,")
    print("       dd_frac breaches the 3% daily cap). Use the +EV 4R combo at LOW fixed risk.")

def lifetime(dR, dmin, r, buffer, N=30000, cap_months=60, block=5, seed=0):
    rng = np.random.default_rng(seed); nD = len(dR); H = cap_months*MONTH
    nb = int(np.ceil(H/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:H]
    R_, Rmin = dR[idx], dmin[idx]
    E = np.ones(N); alive = np.ones(N, bool); wd = np.zeros(N); life = np.zeros(N, int)
    for t in range(H):
        rt = R_[:,t]; rmin = Rmin[:,t]
        dead = alive & (((rmin*r) <= -DAILY) | (E*(1+rmin*r) <= FLOOR))
        life = np.where(alive & dead, t, life); alive &= ~dead
        E = np.where(alive, E*(1+rt*r), E)
        if (t+1) % MONTH == 0:
            take = np.where(alive & (E > 1.0+buffer), E-(1.0+buffer), 0.0); wd += take; E -= take
    life = np.where(alive, H, life)
    return wd.mean()*100, np.median(wd)*100, (life/MONTH).mean(), alive.mean()*100

if __name__ == "__main__":
    main()
