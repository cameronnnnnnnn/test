"""
challengephaseHF/fast_pass.py — FASTEST pass with the 6pm-reopen reversal (1 trade/night).
Objective flips from cost-per-funded to P(pass within N nights). Min-trading-days and
consistency rules now dominate: Apex's 7-day minimum is a hard speed floor; a no-consistency
min-1-day firm can pass on ONE +3R night if risk >= target/3.
Reports P(pass<=5/10/15/20 nights) and blow-by-20 for aggressive risk ladders per firm.
Run: python3 fast_pass.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "news")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
from firm_compare import night_trades, FIRMS               # noqa: E402

NP = 60_000


def mc_times(tri, risk, start, target, dd, mode, daily, cons, min_days,
             n_paths=NP, seed=11, block=5, deadline=20):
    rng = np.random.default_rng(seed)
    n = len(tri)
    nb = int(np.ceil(deadline / block))
    st = rng.integers(0, n, size=(n_paths, nb))
    samp = ((st[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(n_paths, -1)[:, :deadline]
    R, MAE, MFE = tri[samp, 0], tri[samp, 1], tri[samp, 2]
    E = np.full(n_paths, float(start)); peak = np.full(n_paths, float(start))
    sg = np.zeros(n_paths); mg = np.zeros(n_paths)
    passed = np.zeros(n_paths, bool); blown = np.zeros(n_paths, bool)
    tp_ = np.full(n_paths, 10_000)
    for t in range(deadline):
        live = ~passed & ~blown
        if not live.any(): break
        hi = E + MFE[:, t]*risk; lo = E + MAE[:, t]*risk
        if mode == "intraday": floor = np.maximum(peak, hi) - dd
        elif mode == "eod":    floor = peak - dd
        else:                  floor = start - dd
        b = lo <= floor
        if daily > 0: b = b | ((lo - E) <= -daily)
        blown |= live & b
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
        tp_ = np.where(pn & (tp_ > deadline), t+1, tp_)
    return tp_, blown


def main():
    cache = {c: night_trades(c) for c in (1.5, 2.0)}
    print(f"{'firm':30}{'risk':>7} | {'P<=5n':>6}{'P<=10n':>7}{'P<=15n':>7}{'P<=20n':>7}{'blow20':>7}")
    print("-" * 74)
    LADDERS = {
        "Apex 50K":            (560, 800, 1000),
        "TopStep 50K":         (560, 800, 950),
        "EOD-trail 50K (MFFU-style)":     (800, 1000, 1200),
        "STATIC-dd 50K (Tradeify-style)": (800, 1000, 1250),
        "FTMO 15K 1-step":     (225, 300, 400),
        "Goat Blitz 10K":      (150, 200, 250),
    }
    for name, cost, start, tgt, dd, mode, daily, cons, mind, fee, ft, _ in FIRMS:
        tri = cache[cost]
        for r in LADDERS[name]:
            if daily > 0 and r > daily: continue
            tp_, blown = mc_times(tri, r, start, tgt, dd, mode, daily, cons, mind)
            ps = [(tp_ <= k).mean()*100 for k in (5, 10, 15, 20)]
            print(f"{name:30}{r:>6}$ | {ps[0]:5.1f}%{ps[1]:6.1f}%{ps[2]:6.1f}%{ps[3]:6.1f}%{blown.mean()*100:6.1f}%")
        print()


if __name__ == "__main__":
    main()
