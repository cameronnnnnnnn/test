"""
news/combined_system.py — THE COMBINED SYSTEM (high-WR build), the two legs that survived
validation, at their WR-optimal settings:

  LEG 1  6pm reopen REVERSAL : fade the 6:00pm ET reopen candle at 6:01pm. SL 40 / TP 40 (1:1).
         Skip if reopen gap >100pt. Exit 2:55am ET if neither hits.
  LEG 2  9:30 CONTINUATION   : 9:30 candle range >= 25pt -> trade WITH its direction at 9:31.
         SL 50 / TP 62 (1:1.25). Exit 10:55pm server (end of US day) if neither hits.
         (Small 9:30 candles: NO TRADE — the fade only works in the 2025 regime, excluded.)

Both legs land on the same server day (6pm leg = 01:01 server, 9:30 leg = 16:31 server), so the
MC aggregates them sequentially into one daily equity path (intraday trail sees the combination).
Outputs: per-leg + combined WR/expR, and the Apex 50K MC. Run: python3 combined_system.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402

COST = 1.5
OPEN = 16*60 + 30; EOD_DAY = 22*60 + 55
NP = 60_000


def all_trades(nas):
    F = build_days(nas)
    spec1 = ExitSpec(tp_R=1.0, max_bars=600)
    o1 = [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=40.0, spec=spec1,
               eod_bar=int(r.eod), day=r.day, tag="6pm_rev")
          for _, r in F.iterrows() if r.cdir != 0 and abs(r.gap) <= 100]
    tod = nas["tod"].values
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    spec2 = ExitSpec(tp_R=1.25, max_bars=600)
    o2 = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]; ob = gi[t == OPEN]
        if len(ob) != 1: continue
        b0 = ob[0]
        if (h[b0] - l[b0]) < 25.0: continue
        d = np.sign(c[b0] - o[b0])
        if d == 0: continue
        eod = gi[(t > OPEN) & (t <= EOD_DAY)]
        if len(eod) < 60: continue
        o2.append(dict(entry_bar=int(b0), dir=int(d), stop_pts=50.0, spec=spec2,
                       eod_bar=int(eod[-1]), day=day, tag="930_cont"))
    t1 = engine.simulate(nas, o1, cost_pts=COST)
    t2 = engine.simulate(nas, o2, cost_pts=COST)
    return pd.concat([t1, t2], ignore_index=True).sort_values("entry_dt").reset_index(drop=True)


def day_records(tr, all_days):
    """sequential same-$-risk aggregation to one (day_R, day_min, day_max) path per day."""
    recs = {}
    for day, g in tr.groupby("day"):
        cum = 0.0; lo = 0.0; hi = 0.0
        for _, r in g.sort_values("entry_dt").iterrows():
            lo = min(lo, cum + r["mae_R"]); hi = max(hi, cum + r["mfe_R"])
            cum += r["R"]; lo = min(lo, cum); hi = max(hi, cum)
        recs[day] = (cum, lo, hi)
    out = [recs.get(d, (0.0, 0.0, 0.0)) for d in all_days]
    return np.array(out)


def mc_days(dd, risk, start=50_000, target=3000, trail=2500, cons=0.50,
            n_paths=NP, seed=11, block=5, deadline=120):
    rng = np.random.default_rng(seed)
    n = len(dd)
    nb = int(np.ceil(deadline / block))
    st = rng.integers(0, n, size=(n_paths, nb))
    samp = ((st[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(n_paths, -1)[:, :deadline]
    R, LO, HI = dd[samp, 0], dd[samp, 1], dd[samp, 2]
    E = np.full(n_paths, float(start)); peak = np.full(n_paths, float(start))
    sg = np.zeros(n_paths); mg = np.zeros(n_paths)
    passed = np.zeros(n_paths, bool); blown = np.zeros(n_paths, bool)
    tp_ = np.full(n_paths, 10_000)
    for t in range(deadline):
        live = ~passed & ~blown
        if not live.any(): break
        hi = E + HI[:, t]*risk; lo = E + LO[:, t]*risk
        floor = np.maximum(peak, hi) - trail
        blown |= live & (lo <= floor)
        live = ~passed & ~blown
        prof = R[:, t]*risk
        E = np.where(live, E + prof, E)
        peak = np.where(live, np.maximum(np.maximum(peak, hi), E), peak)
        gp = np.where(live & (prof > 0), prof, 0.0)
        sg += gp; mg = np.maximum(mg, gp)
        pn = live & (E >= start + target) & (mg <= cons*sg + 1e-9)
        passed |= pn
        tp_ = np.where(pn & (tp_ > deadline), t+1, tp_)
    return dict(p=passed.mean(), b=blown.mean(),
                p10=(tp_ <= 10).mean(), med=(np.median(tp_[passed]) if passed.any() else np.nan))


def main():
    nas = S.prep(data.load())
    tr = all_trades(nas)
    ad = np.array(sorted(nas.groupby("date").indices.keys()))
    cut = ad[int(len(ad)*0.7)]
    print("COMBINED SYSTEM — 6pm reversal (40/40) + 9:30 big-candle continuation (50/62)\n")
    for tag, g in [*tr.groupby("tag"), ("COMBINED", tr)]:
        gtr = g[g["day"] <= cut]; gte = g[g["day"] > cut]
        e = engine.edge_stats(g)
        print(f"  {tag:9} n={e['n']:4d} ({e['n']/len(ad):.2f}/day)  WR {e['wr']*100:4.1f}%  "
              f"expR {e['expR']:+.3f}   [train {gtr['R'].mean():+.3f} WR {(gtr['R']>0).mean()*100:.1f}% | "
              f"test {gte['R'].mean():+.3f} WR {(gte['R']>0).mean()*100:.1f}%]")
    dd = day_records(tr, ad)
    print(f"\n  day stats: {np.mean(dd[:,0]!=0)*100:.0f}% of days trade;  mean day {dd[:,0].mean():+.3f}R;  "
          f"worst day {dd[:,0].min():+.2f}R (floor -2R by construction)")
    print(f"\nApex 50K MC (both legs same account, intraday trail, 50% consistency):")
    print(f"  {'risk/trade':>11} {'pass%':>7} {'blow%':>7} {'P<=10n':>7} {'med n':>6}")
    for r in (300, 400, 500, 560):
        m = mc_days(dd, r)
        print(f"  {r:>10}$ {m['p']*100:6.1f}% {m['b']*100:6.1f}% {m['p10']*100:6.1f}% {m['med']:>6.0f}")


if __name__ == "__main__":
    main()
