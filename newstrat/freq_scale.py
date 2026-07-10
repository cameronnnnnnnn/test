"""
newstrat/freq_scale.py — iteration 4: the NAS100 fade|prior-day-range edge is real and high-WR
(55%, +0.14) but rare (0.15/day). Can it be made higher-FREQUENCY without diluting to noise? Two
levers: (a) loosen the range-regime threshold (more qualifying days), (b) fade more aggressively
(lower k = more signals). Range cutoff tuned on TRAIN. Report /day + WR + expR train/test for each
— if edge holds as frequency rises, we finally have a higher-freq/higher-WR leg; if it decays,
the ceiling is structural. Run: python3 freq_scale.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
RS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "regimeswitch"))
for p in (V4, RS):
    if p not in sys.path: sys.path.insert(0, p)
import strategies as S, engine                        # noqa: E402
import allinstr, indic                                # noqa: E402


def main():
    D = allinstr.load_all(verbose=False)
    info = D["NAS100"]; df = info["df"]; sm = allinstr.stopmap(info, 0.20)
    f = indic.daily_features(df)                       # causal chop
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    dtr, dte = set(ad[ad <= cut]), set(ad[ad > cut])
    chop_tr = f["chop"].reindex(sorted(dtr)).dropna()

    # range-day definitions (looser -> more days), thresholds from TRAIN only
    defs = {
        "strict (ADX<20 & chop>55)": [d for d in ad if f["adx"].get(d, 99) < 20 and f["chop"].get(d, 0) > 55],
        "chop>q60":  [d for d in ad if f["chop"].get(d, np.nan) > chop_tr.quantile(0.60)],
        "chop>q40":  [d for d in ad if f["chop"].get(d, np.nan) > chop_tr.quantile(0.40)],
        "chop>median": [d for d in ad if f["chop"].get(d, np.nan) > chop_tr.quantile(0.50)],
    }
    print("NAS100 fade|range — frequency vs edge (does the +0.14/55%WR survive more trades?)")
    print(f"  {'range def':26} {'k':>4} {'/day':>5} {'WR':>6} {'expR_tr':>8} {'expR_te':>8} {'n':>5}")
    for k in (2.0, 1.5):
        fade = engine.simulate(df, S.vwap_fade_sel(df, k=k, open_min=16*60, trail_R=2.0,
                               partial_R=1.0, stop_map=sm), cost_pts=info["cost"])
        for name, days in defs.items():
            g = fade[fade["day"].isin(set(days))] if len(fade) else fade
            gtr = g[g["day"].isin(dtr)]; gte = g[g["day"].isin(dte)]
            if not len(g):
                continue
            e = engine.edge_stats(g)
            etr = engine.edge_stats(gtr)["expR"] if len(gtr) else float("nan")
            ete = engine.edge_stats(gte)["expR"] if len(gte) else float("nan")
            flag = "  <-- holds" if (etr > 0.03 and ete > 0.03) else ""
            print(f"  {name:26} {k:>4.1f} {e['n']/len(ad):5.2f} {e['wr']*100:5.1f}% "
                  f"{etr:+8.3f} {ete:+8.3f} {e['n']:>5}{flag}")
        print()
    print("-"*70)
    print("If '/day' rises but expR_te collapses toward 0/negative, the edge doesn't scale (rare by")
    print("nature). If a looser def keeps both expR halves +, that's a higher-frequency high-WR leg.")


if __name__ == "__main__":
    main()
