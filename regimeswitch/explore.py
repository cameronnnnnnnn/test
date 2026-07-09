"""
regimeswitch/explore.py — the honest first cut at the "regime-switch to 88%" idea, on FTMO
15k 1-Step rules (staying on FTMO). Hypothesis worth testing: 52p's worst days are CHOPPY
days (proved in ../challengephaseHF/riskoff.py), so an ADX/Choppiness filter that detects and
SITS OUT choppy/unclear regimes — and swaps in a mean-reversion leg on genuine range days —
should raise the pass rate. This tests it with train(70%)/test(30%), tuning risk on train and
reporting on test, against the plain-52p ~55% baseline. Anything that only wins in-sample is
called out.

Approaches:
  A baseline 52p (all momentum legs, every day)
  B 52p but SIT OUT high prior-day-choppiness days
  C 52p but SIT OUT choppy OPENS (first-hour intraday choppiness high)
  D regime SWITCH: momentum legs on trend/expansion days, a FADE leg on range days, sit out unclear
Run: python3 explore.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, V3, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402
import indic                                          # noqa: E402

COST = 2.0; BREAKER = 2.0; DEADLINE = 20; NP = 40000
RISKS = (0.005, 0.0075, 0.01, 0.0125)


def momo(df):
    return CP52.build(df)                              # the 52p momentum/breakout legs


def fade(df):                                          # range-day mean-reversion legs
    return (S.vwap_fade_sel(df, k=2.0, stop_pts=40, partial_R=1.0, trail_R=2.0)
            + S.or_fade(df, poke_pts=15, stop_pts=40, tp_R=1.5))


def split(ad, frac=0.7):
    cut = ad[int(len(ad) * frac)]
    return ad[ad <= cut], ad[ad > cut]


def best_on(days_tr):
    return max(RISKS, key=lambda r: ftmo.run_mc(days_tr, r, DEADLINE, n_paths=NP, seed=11, block=5)["pass_rate"])


def evaluate(tr_df, ad, tag):
    dtr, dte = split(ad)
    days_tr = build_days(tr_df[tr_df["day"].isin(set(dtr))], dtr, BREAKER)
    days_te = build_days(tr_df[tr_df["day"].isin(set(dte))], dte, BREAKER)
    r = best_on(days_tr)
    mtr = ftmo.run_mc(days_tr, r, DEADLINE, n_paths=NP, seed=11, block=5)
    mte = ftmo.run_mc(days_te, r, DEADLINE, n_paths=NP, seed=11, block=5)
    ndays_traded = tr_df["day"].nunique()
    print(f"  {tag:34} r*={r*100:4.2f}%  passTR {mtr['pass_rate']*100:4.1f}%  "
          f"passTE {mte['pass_rate']*100:4.1f}%  blowTE {mte['blow_rate']*100:4.1f}%  "
          f"days_traded {ndays_traded}")
    return mte["pass_rate"]


def filter_days(tr_df, keep_days):
    return tr_df[tr_df["day"].isin(set(keep_days))]


def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    feats = indic.daily_features(df)                   # causal daily ADX/chop/slope
    ichop = indic.intraday_chop(df, start_min=16*60, win_min=60)   # US-open first hour CI

    momo_tr = engine.simulate(df, momo(df), cost_pts=COST)
    fade_tr = engine.simulate(df, fade(df), cost_pts=COST)

    # regime label per day (standard thresholds, NOT tuned -> avoids first-look overfit)
    reg = {}
    for dt in ad:
        f = feats.loc[dt] if dt in feats.index else None
        if f is None or f["adx"] != f["adx"] or f["chop"] != f["chop"]:
            reg[dt] = "unclear"; continue
        if f["adx"] >= 25 and f["chop"] < 45:
            reg[dt] = "trend"
        elif f["adx"] < 20 and f["chop"] > 55:
            reg[dt] = "range"
        else:
            reg[dt] = "unclear"
    from collections import Counter
    print("regime mix (prior-day ADX/chop):", dict(Counter(reg[d] for d in ad)))
    chop_vals = feats["chop"].reindex(ad)
    q80 = np.nanquantile(chop_vals.values, 0.80)
    ic_vals = pd.Series({d: ichop.get(d, np.nan) for d in ad})
    icq80 = np.nanquantile(ic_vals.values, 0.80)
    print(f"prior-day chop q80={q80:.1f}   intraday-open chop q80={icq80:.1f}\n")

    print("=" * 92)
    print("HONEST train/test 20-day pass — does regime filtering/switching beat plain 52p (~55%)?")
    print("=" * 92)
    # A baseline
    evaluate(momo_tr, ad, "A. 52p baseline (all days)")
    # B sit out high prior-day chop
    keepB = [d for d in ad if not (chop_vals.get(d, np.nan) > q80)]
    evaluate(filter_days(momo_tr, keepB), ad, "B. 52p, skip high prior-day chop")
    # C sit out choppy opens
    keepC = [d for d in ad if not (ic_vals.get(d, np.nan) > icq80)]
    evaluate(filter_days(momo_tr, keepC), ad, "C. 52p, skip choppy opens (1h CI)")
    # D regime switch
    momo_days = [d for d in ad if reg[d] in ("trend", "unclear")]   # momentum on trend + unclear(expansion)
    range_days = [d for d in ad if reg[d] == "range"]
    d_parts = [filter_days(momo_tr, momo_days), filter_days(fade_tr, range_days)]
    evaluate(pd.concat(d_parts, ignore_index=True), ad, "D. regime switch (momo trend / fade range)")
    # D' regime switch but sit out unclear entirely
    momo_only_trend = [d for d in ad if reg[d] == "trend"]
    d2 = [filter_days(momo_tr, momo_only_trend), filter_days(fade_tr, range_days)]
    evaluate(pd.concat(d2, ignore_index=True), ad, "D'. switch + SIT OUT unclear days")
    print("-" * 92)
    print("Read passTE vs the 52p baseline row. Higher TEST pass (not just TRAIN) = real. If the")
    print("filters only lift TRAIN or just cut days without lifting TEST, the regime edge isn't there.")


if __name__ == "__main__":
    main()
