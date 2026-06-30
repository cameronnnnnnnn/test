"""
iter2_probe.py — iteration-1 revealed that high-WR/LOW-RR (the convex/funded geometry)
TIMES OUT on the challenge: it can't reach +10% in 20 days. The challenge needs DRIFT
(positive skew, let winners run) on HIGH-QUALITY entries. This probes the opposite
geometry: feature-FILTERED entries + RUNNER exits (trail / high TP). Run: python3 iter2_probe.py
"""
import numpy as np
import features as FE, data, strategies as S
from strat_gen import eod_map, filtered_orders, report
import warnings; warnings.filterwarnings("ignore")


def main():
    df = S.prep(data.load()); F = FE.compute(df)
    ad = np.array(sorted(df["date"].unique())); eod = eod_map(df)
    R = (0.005, 0.0075, 0.01, 0.0125, 0.015)
    print("=" * 92)
    print("ITER-2 PROBE — feature-filtered entries + RUNNER exits (drift to punch +10% in 20d)")
    print("=" * 92)

    report(df, F, eod, ad, "A) CUSUM with-trend  stop50 trail3R (runner)",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 0.0, trail_R=3.0,
                                   filters=[("vwap_slope", 0.04, np.inf, True)]), risks=R)

    report(df, F, eod, ad, "B) CUSUM with-trend  stop50 tp4R be1R",
           lambda: filtered_orders(df, F, eod, "cusum", 50, 4.0, be_R=1.0,
                                   filters=[("vwap_slope", 0.04, np.inf, True)]), risks=R)

    report(df, F, eod, ad, "C) ORB filtered(min_since_open>24) stop50 tp4R be1R",
           lambda: filtered_orders(df, F, eod, "orb", 50, 4.0, be_R=1.0,
                                   filters=[("min_since_open", 24, np.inf, False)]), risks=R)

    report(df, F, eod, ad, "D) COMBO  CUSUM-trend tp4R + ORB-filt tp4R + VWpull trail3R",
           lambda: (filtered_orders(df, F, eod, "cusum", 50, 4.0, be_R=1.0,
                                    filters=[("vwap_slope", 0.04, np.inf, True)])
                    + filtered_orders(df, F, eod, "orb", 50, 4.0, be_R=1.0,
                                      filters=[("min_since_open", 24, np.inf, False)])
                    + S.vwap_pullback(df, stop_pts=40, tp_R=4.0, trail_R=0.0)), risks=R)

    report(df, F, eod, ad, "E) COMBO higher-RR  CUSUM-trend tp6R + ORB-filt tp6R + VWpull tp6R",
           lambda: (filtered_orders(df, F, eod, "cusum", 50, 6.0, be_R=1.0,
                                    filters=[("vwap_slope", 0.04, np.inf, True)])
                    + filtered_orders(df, F, eod, "orb", 50, 6.0, be_R=1.0,
                                      filters=[("min_since_open", 24, np.inf, False)])
                    + S.vwap_pullback(df, stop_pts=40, tp_R=6.0, trail_R=0.0)), risks=R)


if __name__ == "__main__":
    main()
