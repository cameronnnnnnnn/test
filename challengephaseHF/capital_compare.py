"""
challengephaseHF/capital_compare.py — firm ranking on fee per funded CAPITAL + speed, incl. the
user's Apex 100K @ $84 offer. Two capital lenses:
  * nominal $k (marketing size — matters for CFD firms where max-loss/payout scale with it)
  * funded-account DRAWDOWN $k (the real losable capital of a funded futures account)
Per firm: risk swept; two picks shown — VALUE (min fee per drawdown-capital) and SPEED
(max P(pass<=10 nights)). PARAMS = Jan-2026 knowledge + user's inputs; VERIFY before buying.
Run: python3 capital_compare.py
"""
import os, sys
import numpy as np, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "news")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
from firm_compare import night_trades                       # noqa: E402
from fast_pass import mc_times                              # noqa: E402

#        name                cost start   tgt    dd   mode      daily cons  min fee  ft  nom_k dd_k  risks
FIRMS = [
    ("Apex 100K ($84)",       1.5, 100_000, 6000, 3000, "intraday", 0,   0.50, 7, 84,  "mo", 100, 3.0, (400, 560, 800, 1000, 1200)),
    ("Apex 50K",              1.5, 50_000, 3000, 2500, "intraday",  0,   0.50, 7, 40,  "mo", 50,  2.5, (240, 400, 560, 800)),
    ("TopStep 50K",           1.5, 50_000, 3000, 2000, "eod",     1000,  0.0,  2, 49,  "mo", 50,  2.0, (240, 400, 560, 800, 950)),
    ("MFFU-style 50K",        1.5, 50_000, 3000, 2500, "eod",     1250,  0.0,  1, 80,  "mo", 50,  2.5, (400, 560, 800, 1000, 1200)),
    ("Static-dd 50K",         1.5, 50_000, 3000, 2500, "static",  1250,  0.0,  1, 100, "mo", 50,  2.5, (400, 560, 800, 1000, 1250)),
    ("FTMO 15K",              2.0, 15_000, 1500, 1500, "static",   450,  0.50, 4, 180, "1x", 15,  1.5, (110, 150, 225, 300)),
    ("Goat Blitz 10K",        2.0, 10_000,  300,  500, "static",   300,  0.0,  1, 65,  "1x", 10,  0.5, (50, 100, 150, 200, 250)),
]


def evaluate(tri, r, start, tgt, dd, mode, daily, cons, mind):
    tp_, blown = mc_times(tri, r, start, tgt, dd, mode, daily, cons, mind, deadline=120)
    passed = tp_ <= 120
    p = passed.mean()
    med = np.median(tp_[passed]) if passed.any() else np.nan
    mean_n = tp_[passed].mean() if passed.any() else 120
    p10 = (tp_ <= 10).mean()
    return p, p10, med, mean_n, blown.mean()


def main():
    cache = {c: night_trades(c) for c in (1.5, 2.0)}
    print(f"{'firm / pick':34}{'risk':>6} {'pass%':>6}{'P<=10n':>7}{'med n':>6} | {'$/fund':>7}"
          f"{'$/nom$k':>8}{'$/dd$k':>7}")
    print("-" * 82)
    for name, cost, start, tgt, dd, mode, daily, cons, mind, fee, ft, nomk, ddk, risks in FIRMS:
        tri = cache[cost]
        evs = {}
        for r in risks:
            if daily > 0 and r > daily: continue
            evs[r] = evaluate(tri, r, start, tgt, dd, mode, daily, cons, mind)
        def costf(e):
            p, p10, med, mean_n, bl = e
            months = max(mean_n/21, 1)
            return (fee*months if ft == "mo" else fee) / max(p, 1e-9)
        r_val = min(evs, key=lambda r: costf(evs[r]) / ddk)
        r_spd = max(evs, key=lambda r: evs[r][1])
        for lbl, r in (("value", r_val), ("speed", r_spd)):
            p, p10, med, mean_n, bl = evs[r]
            cf = costf(evs[r])
            print(f"{name+' ['+lbl+']':34}{r:>5}$ {p*100:5.1f}%{p10*100:6.1f}%{med:>6.0f} | {cf:>6.0f}$"
                  f"{cf/nomk:>7.2f}${cf/ddk:>6.0f}$")
        print()
    print("$/nom$k = fee per $1k of NOMINAL funded size; $/dd$k = fee per $1k of funded-account")
    print("DRAWDOWN (the real losable capital of a futures account). VERIFY current firm params.")


if __name__ == "__main__":
    main()
