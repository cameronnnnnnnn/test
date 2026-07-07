"""
challengephaseHF/riskoff.py — hunt for a RISK-OFF / short-biased positive-edge leg. The two
legs that survived last round (USDJPY Tokyo, NAS turn-of-month) are both long-biased trend-
riders, so their day-to-day 0-correlation hides a shared risk-off vulnerability: in a real
sell-off both could fail together, and the worst-fold floor would drop. The fix is a leg that
PAYS when the long book bleeds. NAS100 has volatility asymmetry (down-moves are faster/larger
— "stairs up, elevator down"), so a short-only breakdown, armed only in a bearish / vol-
expansion regime, is the principled candidate.

The decisive test is not standalone expR — it is the CONDITIONAL return on 52p's WORST days:
a real floor-raiser makes money exactly when the core combo is losing. So we report, honestly
(train/test):
  1 standalone edge of the short-regime leg (and vs an unconditional short-only control)
  2 its mean day-R on 52p's worst-quintile days vs overall  (the hedge test)
  3 stacked 52p + short-regime: worst-fold pass vs 52p alone

Run: python3 riskoff.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
V3 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephasev3"))
for p in (V4, V3):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo          # noqa: E402
from search import build_days                        # noqa: E402
from engine import ExitSpec                           # noqa: E402
import ChallengePhase52p as CP52                      # noqa: E402

OPEN = 16 * 60; SESS_END = 22 * 60 + 55
BREAKER = 2.0; DEADLINE = 20


def regimes(df, sma_n=20):
    """Look-ahead-free daily regime flags: bearish trend (prior close < prior SMA) and
    vol-expansion (ATR5 > ATR20, both shifted). Returns {date: bool} maps."""
    g = df.groupby("date").agg(c=("close", "last"), h=("high", "max"), l=("low", "min"))
    sma = g["c"].rolling(sma_n).mean().shift(1)
    bear = (g["c"].shift(1) < sma)
    pc = g["c"].shift(1)
    tr = np.maximum(g["h"] - g["l"], np.maximum((g["h"] - pc).abs(), (g["l"] - pc).abs()))
    atrf = tr.rolling(5).mean().shift(1); atrs = tr.rolling(20).mean().shift(1)
    volx = atrf > atrs
    return bear.to_dict(), volx.to_dict()


def short_break(df, regime=None, or_min=30, stop_pts=50, trail_R=3.0, be_R=0.0,
                open_min=OPEN, entry_by=21*60):
    """Short-only US opening-range breakdown, trailing runner. If regime given, only arm on
    days where regime[day] is True (else the leg is flat that day)."""
    h, l = df["high"].values, df["low"].values
    tod = df["tod"].values
    orders = []
    or_end = open_min + or_min
    for day, gi in df.groupby("date").indices.items():
        if regime is not None and not bool(regime.get(day, False)):
            continue
        t = tod[gi]
        om = (t >= open_min) & (t < or_end)
        if om.sum() < 5:
            continue
        rl = l[gi[om]].min()
        post = gi[(t >= or_end) & (t <= SESS_END)]
        if len(post) < 5:
            continue
        eod = post[-1]
        spec = ExitSpec(tp_R=0.0, be_R=be_R, trail_R=trail_R, max_bars=10**9)
        for b in post[:-1]:
            if tod[b] > entry_by:
                break
            if l[b] <= rl:
                orders.append(dict(entry_bar=b, dir=-1, stop_pts=stop_pts, spec=spec,
                                   eod_bar=eod, day=day, tag="shortbrk")); break
    return orders


def split_dates(df, frac=0.7):
    ad = np.array(sorted(df["date"].unique()))
    cut = ad[int(len(ad) * frac)]
    return ad, set(ad[ad <= cut]), set(ad[ad > cut])


def es_split(tr, dtr, dte, ndays):
    a = engine.edge_stats(tr)
    et = engine.edge_stats(tr[tr["day"].isin(dtr)])["expR"] if len(tr[tr["day"].isin(dtr)]) else float("nan")
    ee = engine.edge_stats(tr[tr["day"].isin(dte)])["expR"] if len(tr[tr["day"].isin(dte)]) else float("nan")
    return a, et, ee


def main():
    df = S.prep(data.load()); ad, dtr, dte = split_dates(df)
    ndays = df["date"].nunique()
    bear, volx = regimes(df)
    both = {d: (bear.get(d, False) and volx.get(d, False)) for d in ad}

    print(f"NAS100 risk-off short leg — {ndays} days.  edge = /day, WR, expR(all/tr/te), PF\n")
    print(f"  {'leg':22} {'/day':>5} {'WR':>6} {'expR':>7} {'exp_tr':>7} {'exp_te':>7} {'PF':>5}")
    variants = {
        "short (all days)":    None,
        "short|bear":          bear,
        "short|volexp":        volx,
        "short|bear&volexp":   both,
    }
    legs = {}
    for nm, reg in variants.items():
        tr = engine.simulate(df, short_break(df, regime=reg), cost_pts=2.0)
        legs[nm] = tr
        if not len(tr):
            print(f"  {nm:22} no trades"); continue
        a, et, ee = es_split(tr, dtr, dte, ndays)
        print(f"  {nm:22} {a['n']/ndays:5.2f} {a['wr']*100:5.1f}% {a['expR']:+7.3f} "
              f"{et:+7.3f} {ee:+7.3f} {a['pf']:5.2f}")

    # ---- the decisive hedge test: return on 52p's WORST days ----
    print("\n" + "="*74)
    print("HEDGE TEST — short-leg mean day-R on 52p's WORST-quintile days vs overall")
    print("(a real floor-raiser is POSITIVE / higher exactly when 52p is losing)")
    print("="*74)
    cp = engine.simulate(df, CP52.build(df), cost_pts=2.0)
    cp_day = build_days(cp, ad, BREAKER)
    cp_R = pd.Series(np.asarray(cp_day["day_R"], float), index=[pd.Timestamp(x) for x in cp_day["day"]])
    q20 = cp_R.quantile(0.20)
    worst = set(cp_R.index[cp_R <= q20])
    print(f"  52p worst-quintile day-R threshold: {q20:+.2f}R  ({len(worst)} days)")
    print(f"  {'leg':22} {'corr w/52p':>11} {'meanR worst':>12} {'meanR all':>11} {'meanR best':>11}")
    q80 = cp_R.quantile(0.80); best = set(cp_R.index[cp_R >= q80])
    for nm, tr in legs.items():
        sd = build_days(tr, ad, BREAKER)
        sR = pd.Series(np.asarray(sd["day_R"], float), index=[pd.Timestamp(x) for x in sd["day"]])
        corr = np.corrcoef(cp_R.values, sR.values)[0, 1]
        mw = sR[[d for d in sR.index if d in worst]].mean()
        mb = sR[[d for d in sR.index if d in best]].mean()
        print(f"  {nm:22} {corr:>11.2f} {mw:>+12.3f} {sR.mean():>+11.3f} {mb:>+11.3f}")

    # ---- stacked pass (worst-fold) ----
    print("\n" + "="*74)
    print("STACKED 20-day pass — 52p vs 52p + short|bear&volexp  (risk on train, folds)")
    print("="*74)
    folds = np.array_split(ad, 4)
    RISKS = (0.005, 0.0075, 0.01)
    def best_risk(days):
        return max(RISKS, key=lambda r: ftmo.run_mc(days, r, DEADLINE, n_paths=30000, seed=11, block=5)["pass_rate"])
    def cdays(trs, days):
        t = pd.concat([x[x["day"].isin(set(days))] for x in trs], ignore_index=True)
        return build_days(t, days, BREAKER)
    def evalstack(trs, tag):
        r = best_risk(cdays(trs, np.array(sorted(dtr))))
        allm = ftmo.run_mc(cdays(trs, ad), r, DEADLINE, n_paths=80000, seed=11, block=5)
        fps = [ftmo.run_mc(cdays(trs, f), best_risk(cdays(trs, np.concatenate([x for x in folds if x[0] != f[0]]))),
                           DEADLINE, n_paths=40000, seed=11, block=5)["pass_rate"] for f in folds]
        print(f"  {tag:30} r*={r*100:4.2f}%  ALL {allm['pass_rate']*100:4.1f}%  blow {allm['blow_rate']*100:4.1f}%"
              f"  | folds mean {np.mean(fps)*100:4.1f}% worst {np.min(fps)*100:4.1f}%")
    evalstack([cp], "52p alone")
    evalstack([cp, legs["short|bear&volexp"]], "52p + short|bear&volexp")
    evalstack([cp, legs["short|bear"]], "52p + short|bear")
    print("-"*74)
    print("Verdict: the short-regime leg earns its place ONLY if it is +EV (or ~0EV) AND makes")
    print("money on 52p's worst days (negative corr / positive worst-day R), lifting worst-fold.")


if __name__ == "__main__":
    main()
