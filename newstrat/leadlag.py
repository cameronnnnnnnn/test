"""
newstrat/leadlag.py — loop iteration 8: cross-index LEAD-LAG mining. Mechanism: index-arbitrage
propagation — a sharp move in one index can drag a correlated index with a delay. If NAS100's
last-5-minutes move predicts GER40's next 5 minutes (or vice versa), that's a real, high-frequency,
mechanically-grounded signal. Also: weekday seasonality (day-of-week drift + 52p expR by weekday).

Protocol as always: TRAIN-only selection, one-shot TEST check, non-overlapping sampling (every
5th minute) so t-stats aren't autocorrelation-inflated, magnitudes vs cost. Run: python3 leadlag.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, fx_data          # noqa: E402
import ChallengePhase52p as CP52                        # noqa: E402

K = 5   # signal/response horizon (minutes)


def main():
    nas = S.prep(data.load()); ger = S.prep(fx_data.load("GER40"))
    aN = S.daily_atr(nas, 14); aG = S.daily_atr(ger, 14)
    j = nas[["close"]].join(ger[["close"]], how="inner", lsuffix="_n", rsuffix="_g").dropna()
    j["date"] = j.index.normalize()
    j["tod"] = j.index.hour*60 + j.index.minute
    j["atr_n"] = j["date"].map(aN); j["atr_g"] = j["date"].map(aG)
    j = j[(j["atr_n"] > 0) & (j["atr_g"] > 0)]
    ad = np.array(sorted(j["date"].unique())); cut = ad[int(len(ad)*0.7)]
    print(f"aligned bars: {len(j):,}  days: {len(ad)}  (train cut {pd.Timestamp(cut).date()})")

    cn = j["close_n"].values; cg = j["close_g"].values
    dsame = np.zeros(len(j), bool)
    rN = np.full(len(j), np.nan); rG = np.full(len(j), np.nan); fG = np.full(len(j), np.nan); fN = np.full(len(j), np.nan)
    rN[K:] = (cn[K:]/cn[:-K]-1); rG[K:] = (cg[K:]/cg[:-K]-1)
    fG[:-K] = (cg[K:]/cg[:-K]-1); fN[:-K] = (cn[K:]/cn[:-K]-1)
    dates = j["date"].values
    ok = np.zeros(len(j), bool); ok[K:-K] = (dates[K:-K] == dates[:-2*K]) & (dates[K:-K] == dates[2*K:])
    # normalize by ATR fraction
    rN = rN/(j["atr_n"]/j["close_n"]).values; fN = fN/(j["atr_n"]/j["close_n"]).values
    rG = rG/(j["atr_g"]/j["close_g"]).values; fG = fG/(j["atr_g"]/j["close_g"]).values
    tod = j["tod"].values; train = dates <= cut
    samp = (tod % K == 0)

    def xcorr(sig, resp, lo, hi, label):
        m = ok & samp & train & (tod >= lo) & (tod < hi) & np.isfinite(sig) & np.isfinite(resp)
        n = m.sum()
        rho = np.corrcoef(sig[m], resp[m])[0, 1]
        t = rho*np.sqrt((n-2)/(1-rho**2))
        m2 = ok & samp & ~train & (tod >= lo) & (tod < hi) & np.isfinite(sig) & np.isfinite(resp)
        rho2 = np.corrcoef(sig[m2], resp[m2])[0, 1] if m2.sum() > 500 else np.nan
        # tradeable magnitude: mean response in top/bottom decile of signal (train + test)
        q_hi = np.quantile(sig[m], 0.9); q_lo = np.quantile(sig[m], 0.1)
        mu_hi = resp[m & (sig >= q_hi)].mean(); mu_lo = resp[m & (sig <= q_lo)].mean()
        mu_hi2 = resp[m2 & (sig >= q_hi)].mean() if m2.sum() > 500 else np.nan
        mu_lo2 = resp[m2 & (sig <= q_lo)].mean() if m2.sum() > 500 else np.nan
        print(f"  {label:34} n={n:6d}  rho={rho:+.3f} t={t:+6.1f}  test_rho={rho2:+.3f}   "
              f"top10%: {mu_hi:+.4f}/{mu_hi2:+.4f}  bot10%: {mu_lo:+.4f}/{mu_lo2:+.4f}")
        return rho, rho2

    print(f"\nCROSS-INDEX LEAD-LAG ({K}m signal -> next {K}m response, ATR units, top/bot decile train/test):")
    xcorr(rN, fG, 16*60+30, 22*60, "NAS(-5m) -> GER40(+5m)  US overlap")
    xcorr(rG, fN, 16*60+30, 22*60, "GER40(-5m) -> NAS(+5m)  US overlap")
    xcorr(rN, fG, 10*60, 16*60,    "NAS(-5m) -> GER40(+5m)  EU morning")
    xcorr(rG, fN, 10*60, 16*60,    "GER40(-5m) -> NAS(+5m)  EU morning")
    # contemporaneous corr for context
    m = ok & samp & train & (tod >= 16*60+30) & (tod < 22*60) & np.isfinite(rN) & np.isfinite(rG)
    print(f"  (contemporaneous NAS~GER 5m corr in US overlap: {np.corrcoef(rN[m], rG[m])[0,1]:+.2f})")
    gc = 1.5/np.nanmedian(list(aG.values()))
    print(f"  (GER40 round-turn cost ≈ {gc:.4f} ATR — a decile response must clear this to trade)")

    # ---------------- weekday seasonality ----------------
    print("\nWEEKDAY SEASONALITY:")
    sess = []
    for day, gi in nas.groupby("date").indices.items():
        t = nas["tod"].values[gi]
        s = gi[(t >= 16*60+30) & (t <= 22*60+55)]
        a = aN.get(day, np.nan)
        if len(s) < 200 or not (a == a): continue
        sess.append((day, pd.Timestamp(day).dayofweek, (nas["close"].values[s[-1]]-nas["open"].values[s[0]])/a))
    zz = pd.DataFrame(sess, columns=["day", "wd", "r"])
    ztr = zz[zz["day"] <= cut]; zte = zz[zz["day"] > cut]
    names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for w in range(5):
        g = ztr[ztr["wd"] == w]["r"]; gte = zte[zte["wd"] == w]["r"]
        t_ = g.mean()/(g.std()/np.sqrt(len(g)))
        print(f"  {names[w]}: US-session ret train={g.mean():+.4f}ATR t={t_:+.1f}  test={gte.mean():+.4f}  n={len(g)}")
    p52 = engine.simulate(nas, CP52.build(nas), cost_pts=2.0)
    p52["wd"] = pd.to_datetime(p52["day"]).dt.dayofweek
    print("  52p expR by weekday (train | test):")
    for w in range(5):
        g = p52[(p52["wd"] == w) & (p52["day"] <= cut)]; gte = p52[(p52["wd"] == w) & (p52["day"] > cut)]
        print(f"  {names[w]}: {engine.edge_stats(g)['expR']:+.3f} (n{len(g)}) | "
              f"{engine.edge_stats(gte)['expR'] if len(gte)>30 else float('nan'):+.3f} (n{len(gte)})")


if __name__ == "__main__":
    main()
