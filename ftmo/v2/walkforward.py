"""
walkforward.py — pre-deployment robustness for the 3-setup combo.

PART A  Walk-forward optimization (expanding window): on each in-sample block,
        re-pick the key params (Setup-A stop, fade z) that maximize the 4-week
        FTMO pass, then score those params on the NEXT, unseen block. The spread
        of out-of-sample pass rates across folds = how much regime matters, and
        the IS-vs-OOS gap = how much the fitting overfits.

PART B  Bootstrap confidence band: block-bootstrap the 3 years of trading days
        many times; each replicate -> a 4-week pass rate. The 5-95th percentiles
        are the confidence band on the headline number.

Writes walkforward.png and prints a summary.  Run: python3 walkforward.py
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import strategies as S, engine, ftmo, data
from run import build_days

COST = 3.0; RISK = 0.01; T4 = 20      # 4-week deadline
STOPS_A = [40, 50, 60]; FADE_K = [1.5, 2.0, 2.5]   # the grid we re-optimize over
B_base = dict(stop_pts=40, trail_R=3.0, partial_R=2.0, partial_frac=0.5)

def daysrec(trades, dates):
    base = pd.DataFrame({"day": dates, "day_R": 0.0, "day_min_R": 0.0, "n": 0}).set_index("day")
    if len(trades):
        agg = engine.trades_to_days(trades, dates).set_index("day")
        base.loc[agg.index, ["day_R","day_min_R","n"]] = agg[["day_R","day_min_R","n"]].values
    return base.reset_index().to_records(index=False)

def passrate(trades, dates, T=T4, r=RISK, npaths=15000):
    return ftmo.run_mc(daysrec(trades, dates), r, T, n_paths=npaths, seed=5)["pass_rate"]

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    A = dict(open_min=16*60, or_min=15, tp_R=0.0, be_R=0.0, trail_R=3.0,
             vol_filter=True, partial_R=2.0, partial_frac=0.67)
    C = dict(stop_pts=40, trail_R=2.0, partial_R=1.0, partial_frac=0.5)

    # pre-simulate each param value ONCE on the full series, then filter by date per fold
    print("simulating param grid ...")
    trA = {s: engine.simulate(df, S.orb(df, stop_pts=s, **A), cost_pts=COST) for s in STOPS_A}
    trB = engine.simulate(df, S.vwap_pullback(df, **B_base), cost_pts=COST)
    trC = {k: engine.simulate(df, S.vwap_fade_sel(df, k=k, **C), cost_pts=COST) for k in FADE_K}

    def combo(sA, kC):
        return pd.concat([trA[sA], trB, trC[kC]], ignore_index=True)

    # ---- PART A: walk-forward optimization, expanding window over 6 blocks ----
    nB = 6
    bounds = [ad[i*len(ad)//nB] for i in range(nB)] + [ad[-1] + np.timedelta64(1,"D")]
    print("\nPART A — walk-forward optimization (expanding IS -> next OOS block)")
    print(f"{'OOS period':28s} {'best params':16s} {'IS pass':>8} {'OOS pass':>9}")
    fold_oos, fold_is, fold_lbl = [], [], []
    for i in range(1, nB):
        is_dates  = ad[(ad >= bounds[0]) & (ad < bounds[i])]
        oos_dates = ad[(ad >= bounds[i]) & (ad < bounds[i+1])]
        if len(oos_dates) < 20: continue
        # re-optimize on in-sample
        best = None
        for sA in STOPS_A:
            for kC in FADE_K:
                tr = combo(sA, kC)
                tr_is = tr[(tr.entry_dt >= bounds[0]) & (tr.entry_dt < bounds[i])]
                p_is = passrate(tr_is, is_dates)
                if best is None or p_is > best[0]:
                    best = (p_is, sA, kC)
        p_is, sA, kC = best
        tr = combo(sA, kC)
        tr_oos = tr[(tr.entry_dt >= bounds[i]) & (tr.entry_dt < bounds[i+1])]
        p_oos = passrate(tr_oos, oos_dates)
        lbl = f"{pd.Timestamp(oos_dates[0]).date()}..{pd.Timestamp(oos_dates[-1]).date()}"
        print(f"{lbl:28s} stopA={sA} k={kC:<4} {p_is*100:7.1f}% {p_oos*100:8.1f}%")
        fold_oos.append(p_oos); fold_is.append(p_is); fold_lbl.append(lbl)
    fold_oos = np.array(fold_oos)
    print(f"\n  OOS pass across folds: mean {fold_oos.mean()*100:.1f}%  "
          f"min {fold_oos.min()*100:.1f}%  max {fold_oos.max()*100:.1f}%  std {fold_oos.std()*100:.1f}pp")
    print(f"  mean IS-OOS gap (overfit): {(np.array(fold_is).mean()-fold_oos.mean())*100:.1f}pp")

    # ---- PART B: bootstrap confidence band on the fixed strategy ----
    print("\nPART B — block-bootstrap confidence band (fixed params stopA=50,k=2.0)")
    tr_fix = combo(50, 2.0)
    full = daysrec(tr_fix, ad)
    rng = np.random.default_rng(1); Bn = 400; block = 10; nD = len(full)
    ps = []
    for b in range(Bn):
        idx = []
        while len(idx) < nD:
            s = rng.integers(0, nD); idx.extend(range(s, min(s+block, nD)))
        res = full[np.array(idx[:nD])]
        ps.append(ftmo.run_mc(res, RISK, T4, n_paths=8000, seed=b)["pass_rate"])
    ps = np.array(ps)*100
    lo, med, hi = np.percentile(ps, [5, 50, 95])
    point = passrate(tr_fix, ad, npaths=40000)*100
    print(f"  4-week pass: point estimate {point:.1f}%")
    print(f"  bootstrap median {med:.1f}%   90% CI [{lo:.1f}%, {hi:.1f}%]")

    # ---- chart ----
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    x = np.arange(len(fold_oos))
    ax1.plot(x, np.array(fold_is)*100, "o--", color="gray", label="in-sample (fitted)")
    ax1.plot(x, fold_oos*100, "o-", color="C0", lw=2, label="out-of-sample (unseen)")
    ax1.axhspan(lo, hi, color="C0", alpha=0.12, label=f"bootstrap 90% CI [{lo:.0f},{hi:.0f}]")
    ax1.axhline(80, color="green", ls="--", label="80% target")
    ax1.set_xticks(x); ax1.set_xticklabels([l.split("..")[0] for l in fold_lbl], rotation=30, fontsize=8)
    ax1.set_ylabel("4-week pass rate (%)"); ax1.set_ylim(0, 100)
    ax1.set_title("Walk-forward: in-sample vs unseen OOS pass rate"); ax1.legend(fontsize=8); ax1.grid(alpha=0.3)
    ax2.hist(ps, bins=30, color="C0", alpha=0.8)
    for v, c, t in [(lo,"red","5%"),(med,"black","median"),(hi,"red","95%")]:
        ax2.axvline(v, color=c, ls="--"); ax2.text(v, ax2.get_ylim()[1]*0.9, f" {t}\n {v:.0f}%", fontsize=8)
    ax2.axvline(80, color="green", ls="-", lw=2); ax2.set_xlabel("4-week pass rate (%)")
    ax2.set_title(f"Bootstrap distribution ({Bn} resamples)"); ax2.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig("walkforward.png", dpi=120)

    print("\n" + "="*60)
    print("VERDICT")
    print("="*60)
    print(f"  Fixed-strategy 4-week pass: {point:.0f}%  (90% CI {lo:.0f}-{hi:.0f}%)")
    print(f"  Walk-forward OOS (re-optimized each fold): mean {fold_oos.mean()*100:.0f}%, "
          f"range {fold_oos.min()*100:.0f}-{fold_oos.max()*100:.0f}%")
    print(f"  Overfit gap IS->OOS: {(np.array(fold_is).mean()-fold_oos.mean())*100:.1f}pp")
    print("  chart -> walkforward.png")

if __name__ == "__main__":
    main()
