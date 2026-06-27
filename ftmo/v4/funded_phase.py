"""
v4/funded_phase.py — FUNDED-phase strategy: consistency over speed.

Objective is NOT to race +10%; it's to make a steady profit every month. Target:
>=90% of rolling 30-day (21-trading-day) windows finish >=+3%, while never breaching
the 3% daily / 10% overall loss limits. We measure P(window>=3%), the 10th-percentile
month, P(any loss), and blow-up, by block-bootstrapping the strategy's daily returns,
and search configs/risk that maximise monthly consistency.
"""
import numpy as np, pandas as pd, strategies as S, engine, data
from run import build_days

TDAYS = 21          # ~30 calendar days
DAILY = 0.03; FLOOR = 0.10

def funded_mc(days, risk, N=40000, block=5, seed=0, lock=0.0):
    """Bootstrap 21-day windows; sim equity with 3% daily + 10% overall (death).
    lock>0: stop trading for the month once cumulative profit >= lock (lock it green).
    Return terminal returns (death -> the breach level) and a blow mask."""
    rng = np.random.default_rng(seed)
    dR = np.asarray(days["day_R"], float); dmin = np.asarray(days["day_min_R"], float)
    nD = len(dR)
    nb = int(np.ceil(TDAYS/block))
    starts = rng.integers(0, nD, size=(N, nb))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % nD).reshape(N, -1)[:, :TDAYS]
    R_, Rmin = dR[idx], dmin[idx]
    E = np.ones(N); alive = np.ones(N, bool); locked = np.zeros(N, bool)
    for t in range(TDAYS):
        active = alive & ~locked
        rmin = Rmin[:, t]; rt = R_[:, t]
        daily_breach = (rmin*risk) <= -DAILY
        overall_breach = E*(1+rmin*risk) <= (1-FLOOR)
        dead = active & (daily_breach | overall_breach)
        E = np.where(dead, E*(1+rmin*risk), E)
        alive &= ~dead
        active = alive & ~locked
        E = np.where(active, E*(1+rt*risk), E)
        if lock > 0:
            locked |= (E >= 1.0 + lock)              # lock the month once target hit
    ret = E - 1.0
    return ret, ~alive

def report(name, days, risks):
    for r in risks:
        ret, blow = funded_mc(days, r)
        p3 = (ret >= 0.03).mean(); p0 = (ret >= 0).mean()
        print(f"  {name:22s} r={r*100:.2f}%: P(>=3%)={p3*100:4.1f}%  P(>=0)={p0*100:4.1f}%  "
              f"blow={blow.mean()*100:4.1f}%  p10={np.percentile(ret,10)*100:+5.1f}%  "
              f"mean={ret.mean()*100:+5.1f}%")

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    A = lambda **k: S.orb(df, open_min=16*60, or_min=15, vol_filter=True, trail_R=0.0, **k)
    B = lambda **k: S.vwap_pullback(df, trail_R=0.0, **k)
    configs = {
        "4R combo (challenge)": A(stop_pts=50, tp_R=4.0, be_R=0.0) + B(stop_pts=40, tp_R=4.0),
        "tp2 combo":            A(stop_pts=50, tp_R=2.0, be_R=0.0) + B(stop_pts=40, tp_R=2.0),
        "tp1.5 combo":          A(stop_pts=50, tp_R=1.5, be_R=0.0) + B(stop_pts=40, tp_R=1.5),
        "tp1 combo (hi-WR)":    A(stop_pts=50, tp_R=1.0, be_R=0.0) + B(stop_pts=40, tp_R=1.0),
        "tp1 be0.5 combo":      A(stop_pts=50, tp_R=1.0, be_R=0.5) + B(stop_pts=40, tp_R=1.0),
    }
    print("FUNDED-PHASE consistency — P(30-day window >= +3%). Target >=90%. (cost 2pt)")
    for name, orders in configs.items():
        tr = engine.simulate(df, orders, cost_pts=2.0)
        es = engine.edge_stats(tr); days = build_days(tr, ad)
        print(f" [{name}] WR={es['wr']*100:.0f}% expR={es['expR']:+.3f}")
        report(name, days, [0.0025, 0.005, 0.0075, 0.01])

    # --- recommended: only positive-EV config (4R) + monthly profit-LOCK at +3% ---
    print("\n" + "="*78)
    print("RECOMMENDED funded config: 4R combo + monthly profit-LOCK at +3% (lock month green)")
    print("="*78)
    o = A(stop_pts=50, tp_R=4.0, be_R=0.0) + B(stop_pts=40, tp_R=4.0)
    days = build_days(engine.simulate(df, o, cost_pts=2.0), ad)
    print("  risk    P(>=3%)  blow   P(>=0)  mean   <- pick risk for return-vs-preservation")
    for r in [0.0025, 0.0035, 0.005, 0.0075]:
        ret, bl = funded_mc(days, r, lock=0.03)
        print(f"  {r*100:.2f}%   {(ret>=0.03).mean()*100:5.1f}%  {bl.mean()*100:4.1f}%  "
              f"{(ret>=0).mean()*100:5.1f}%  {ret.mean()*100:+5.2f}%")
    print("\nVERDICT: 90% of months >=3% is NOT achievable on NAS100 (mean caps ~2%, needs")
    print(" monthly Sharpe ~3 / daily ~0.7 vs NAS ~0.05). With the +3% lock, the best honest")
    print(" funded outcome is ~50-65% of months >=3%, traded off against account-blow risk.")
    print(" For PRESERVATION (keep the account you paid to get): r~0.35% -> low blow, ~+1%/mo,")
    print(" break-even (your 2.45%) in ~2-3 months then net profit. Higher risk = more 3%")
    print(" months but real chance of losing the account. NAS's thin edge caps funded too.")

if __name__ == "__main__":
    main()
