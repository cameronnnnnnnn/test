"""
challengephaseHF/firm_compare.py — which prop-firm STRUCTURE fits the 6pm-reopen reversal stats
(46.8% WR, avg win +1.18R, avg loss -0.82R, heavy EOD-exit MFE giveback, 1 trade/night)?

Same bootstrap MC as apex_eval, generalized: target / drawdown amount / drawdown mode
(intraday-trail, EOD-trail, static) / daily limit / consistency / min days / fees.
Futures firms use the 1.5pt-cost trades; CFD firms the 2.0pt-cost version.

PARAMS ARE MY BEST KNOWLEDGE (Jan-2026 cutoff) — VERIFY CURRENT RULES/FEES BEFORE BUYING.
Run: python3 firm_compare.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "news")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine                        # noqa: E402
from engine import ExitSpec                                  # noqa: E402
from reopen_trade import build_days                          # noqa: E402

NIGHTS = 120; NP = 40_000


def night_trades(cost):
    nas = S.prep(data.load())
    F = build_days(nas)
    spec = ExitSpec(tp_R=3.0, be_R=0.0, trail_R=0.0, max_bars=600)
    orders = [dict(entry_bar=int(r.b0), dir=int(-r.cdir), stop_pts=40.0, spec=spec,
                   eod_bar=int(r.eod), day=r.day, tag="rev")
              for _, r in F.iterrows() if r.cdir != 0]
    tr = engine.simulate(nas, orders, cost_pts=cost).sort_values("entry_dt")
    return tr[["R", "mae_R", "mfe_R"]].values


def mc(tri, risk, start, target, dd, mode, daily=0.0, cons=0.0, min_days=1,
       n_paths=NP, seed=11, block=5, deadline=NIGHTS):
    rng = np.random.default_rng(seed)
    n = len(tri)
    nb = int(np.ceil(deadline / block))
    st = rng.integers(0, n, size=(n_paths, nb))
    samp = ((st[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(n_paths, -1)[:, :deadline]
    R, MAE, MFE = tri[samp, 0], tri[samp, 1], tri[samp, 2]
    E = np.full(n_paths, float(start)); peak = np.full(n_paths, float(start))
    sg = np.zeros(n_paths); mg = np.zeros(n_paths)
    passed = np.zeros(n_paths, bool); blown = np.zeros(n_paths, bool)
    tp_ = np.full(n_paths, -1)
    for t in range(deadline):
        live = ~passed & ~blown
        if not live.any(): break
        hi = E + MFE[:, t]*risk; lo = E + MAE[:, t]*risk
        if mode == "intraday": floor = np.maximum(peak, hi) - dd
        elif mode == "eod":    floor = peak - dd
        else:                  floor = start - dd
        b = lo <= floor
        if daily > 0: b = b | ((lo - E) <= -daily)
        blow_now = live & b
        blown |= blow_now
        live = ~passed & ~blown
        prof = R[:, t]*risk
        E = np.where(live, E + prof, E)
        if mode == "intraday": peak = np.where(live, np.maximum(np.maximum(peak, hi), E), peak)
        elif mode == "eod":    peak = np.where(live, np.maximum(peak, E), peak)
        gp = np.where(live & (prof > 0), prof, 0.0)
        sg += gp; mg = np.maximum(mg, gp)
        ok = (mg <= cons*sg + 1e-9) if cons > 0 else True
        pn = live & (E >= start + target) & ok & (t+1 >= min_days)
        passed |= pn
        tp_ = np.where(pn & (tp_ < 0), t+1, tp_)
    return dict(p=passed.mean(), b=blown.mean(),
                med=(np.median(tp_[passed]) if passed.any() else np.nan),
                mean=(tp_[passed].mean() if passed.any() else np.nan))


FIRMS = [
    # name, cost_pts, start, target, dd, mode, daily, cons, min_days, fee, fee_type, risks($)
    ("Apex 50K",            1.5, 50_000, 3000, 2500, "intraday", 0,    0.50, 1, 40,  "mo", (240, 400, 560, 800)),
    ("TopStep 50K",         1.5, 50_000, 3000, 2000, "eod",      1000, 0.0,  2, 49,  "mo", (240, 400, 560, 800)),
    ("EOD-trail 50K (MFFU-style)", 1.5, 50_000, 3000, 2500, "eod", 1250, 0.0, 1, 80, "mo", (240, 400, 560, 800)),
    ("STATIC-dd 50K (Tradeify-style)", 1.5, 50_000, 3000, 2500, "static", 1250, 0.0, 1, 100, "mo", (240, 400, 560, 800)),
    ("FTMO 15K 1-step",     2.0, 15_000, 1500, 1500, "static",   450,  0.50, 4, 180, "1x", (75, 110, 150, 225)),
    ("Goat Blitz 10K",      2.0, 10_000,  300,  500, "static",   300,  0.0,  1, 65,  "1x", (50, 100, 150, 250)),
]


def main():
    cache = {c: night_trades(c) for c in (1.5, 2.0)}
    print(f"{'firm':34}{'best risk':>10}{'pass%':>7}{'blow%':>7}{'med n':>6}{'$/funded':>10}")
    print("-" * 76)
    rows = []
    for name, cost, start, tgt, dd, mode, daily, cons, mind, fee, ft, risks in FIRMS:
        tri = cache[cost]
        best = None
        for r in risks:
            if daily > 0 and r > daily: continue
            m = mc(tri, r, start, tgt, dd, mode, daily, cons, mind)
            months = (m["mean"]/21) if m["mean"] == m["mean"] else 6
            cf = (fee*max(months, 1) if ft == "mo" else fee) / max(m["p"], 1e-9)
            if best is None or cf < best[2]: best = (r, m, cf)
        r, m, cf = best
        rows.append((cf, name, r, m))
        print(f"{name:34}{r:>9}$ {m['p']*100:6.1f}%{m['b']*100:6.1f}%{m['med']:>6.0f}{cf:>9.0f}$")
    print("\nranked by cost-per-funded:", " > ".join(n for _, n, _, _ in sorted(rows)))
    print("VERIFY current rules/fees — knowledge cutoff Jan 2026; firms change these monthly.")


if __name__ == "__main__":
    main()
