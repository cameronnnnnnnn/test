"""
challengephasev3/final_mc.py — 100k-path MC of the ROBUST cross-family winner from
validate.py: EU-open ORB (30m, 50pt, 4R) + US-open ORB (30m, 60pt, 3R) + VWAP pullback
(40pt, 8R), all BE-managed, with a -2R daily circuit breaker, 1.0% risk. Metric: pass
within 20 TRADING DAYS (1 real month) under FTMO 1-Step. Reports all-data + the 4 CV
folds + a short deadline-sensitivity, and writes challengephasev3_final.png.
Run: python3 final_mc.py
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S, engine, ftmo
import search as SR
import warnings; warnings.filterwarnings("ignore")

N = 100_000; BREAKER = 2.0; RISK = 0.01


def winner_trades(df):
    o = (S.orb(df, open_min=11*60, or_min=30, stop_pts=50, tp_R=4.0, be_R=1.0, vol_filter=True)
         + S.orb(df, open_min=16*60, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
         + S.vwap_pullback(df, stop_pts=40, tp_R=8.0, trail_R=0.0))
    return engine.simulate(df, o, cost_pts=2.0)


def run(tr, ad_uni, risk=RISK, deadline=20, n=N):
    d = SR.build_days(tr, ad_uni, BREAKER)
    return ftmo.run_mc(d, risk, deadline, n_paths=n, seed=11, block=5)


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    tr = winner_trades(df); es = engine.edge_stats(tr)
    m = run(tr, ad)
    print("=" * 78)
    print("challengephasev3 ROBUST WINNER — 100k MC, pass within 20 trading days")
    print("EU-ORB 4R + US-ORB 3R + VWpull 8R, -2R breaker, 1.0% risk")
    print(f"edge: WR {es['wr']*100:.1f}%  expR {es['expR']:+.3f}  PF {es['pf']:.2f}  ({es['n']} trades)")
    print("=" * 78)
    print(f"  PASS (+10% in 20d) : {m['pass_rate']*100:5.1f}%")
    print(f"  BLOW               : {m['blow_rate']*100:5.1f}%   (daily-cap share {m['blow_daily_share']*100:.0f}%)")
    print(f"  timeout at 20d     : {m['timeout_rate']*100:5.1f}%")
    print(f"  median days-to-pass: {m['med_days_to_pass']:.0f}")
    print("-" * 78)
    # 4 folds
    k = 4; n = len(ad); folds = [ad[i*n//k:(i+1)*n//k] for i in range(k)]
    fp = [run(tr, fd)["pass_rate"] for fd in folds]
    print(f"  per-fold pass (robustness): [{'  '.join(f'{x*100:.1f}%' for x in fp)}]  "
          f"min {min(fp)*100:.1f}%  mean {np.mean(fp)*100:.1f}%")
    # deadline sensitivity
    dls = [15, 20, 30, 40, 60]
    dp = [(dl, run(tr, ad, deadline=dl)) for dl in dls]
    print("-" * 78)
    print("  deadline sensitivity (all-data):")
    for dl, mm in dp:
        print(f"     {dl:2d}d: pass {mm['pass_rate']*100:5.1f}%  blow {mm['blow_rate']*100:5.1f}%  timeout {mm['timeout_rate']*100:5.1f}%")

    # ---- chart ----
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    a = ax[0]
    vals = [m["pass_rate"]*100, m["blow_rate"]*100, m["timeout_rate"]*100]
    a.bar(["pass", "blow", "timeout"], vals, color=["#55a868", "#c44e52", "#8172b3"])
    for i, v in enumerate(vals): a.text(i, v+0.8, f"{v:.1f}%", ha="center")
    a.set_title("Outcome within 20 trading days"); a.set_ylabel("% of attempts"); a.grid(alpha=.2, axis="y")
    a = ax[1]
    a.bar([f"F{i+1}" for i in range(k)], [x*100 for x in fp], color="#4c72b0")
    a.axhline(np.mean(fp)*100, color="black", ls="--", label=f"mean {np.mean(fp)*100:.0f}%")
    a.axhline(44, color="red", ls=":", label="~44% ceiling")
    for i, x in enumerate(fp): a.text(i, x*100+0.8, f"{x*100:.0f}%", ha="center", fontsize=9)
    a.set_title("Pass by CV time-fold (robustness)"); a.set_ylabel("20d pass %"); a.legend(fontsize=8); a.grid(alpha=.2, axis="y")
    a = ax[2]
    a.plot([d for d, _ in dp], [mm["pass_rate"]*100 for _, mm in dp], "o-", color="#55a868", label="pass")
    a.plot([d for d, _ in dp], [mm["blow_rate"]*100 for _, mm in dp], "o-", color="#c44e52", label="blow")
    a.axvline(20, color="grey", ls=":"); a.set_title("Pass/blow vs deadline"); a.set_xlabel("trading-day deadline")
    a.set_ylabel("%"); a.legend(fontsize=8); a.grid(alpha=.2)
    fig.suptitle("challengephasev3 robust winner — EU-ORB + US-ORB + VWpull, -2R breaker, 1% risk (100k paths)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95]); fig.savefig("challengephasev3_final.png", dpi=120)
    print("\nchart -> challengephasev3_final.png")


if __name__ == "__main__":
    main()
