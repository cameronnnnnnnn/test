"""
news/fairwick.py — does the OPENING candle's wick-to-body ratio predict whether price returns
to the pre-candle close ("fair price")?

Q1  Reference candle = the 9:30 ET open candle (16:30 server) — OR the 8:30 ET candle (15:30
    server) on days with red-folder (high-impact USD) news at 8:30, per the user's rule.
    fair = close of the minute BEFORE the reference candle (9:29 / 8:29).
    For each day: wick-to-body ratio of the reference candle, displacement direction
    (close vs fair), and whether price trades back through fair within 90/120 minutes.
    Output: point-biserial + Spearman correlation, and a quartile bucket table.

Q2  Same for the 6pm ET candle (01:00 server = the reopen after the 5-6pm ET closed hour,
    empirically verified by the coverage gap). fair = last close before the break. Plus a
    volatility profile of that candle (range/body/gap vs the average 1m candle).

Needs the NAS100 M1 data (ftmo/v4/data.py). Run: python3 fairwick.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S                               # noqa: E402

CAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usd_high_impact.csv")
SERVER_TZ = "Europe/Bucharest"
NY_OPEN = 16*60 + 30                                       # 9:30 ET
NEWS_MIN = 15*60 + 30                                      # 8:30 ET
HORIZONS = (90, 120)


def red_news_days():
    df = pd.read_csv(CAL)
    df = df[df["Impact"].str.contains("High", na=False)]
    dt = pd.to_datetime(df["DateTime"], utc=True).dt.tz_convert(SERVER_TZ).dt.tz_localize(None)
    at830 = dt[(dt.dt.hour*60 + dt.dt.minute) == NEWS_MIN]
    return set(at830.dt.normalize().unique())


def wick_body(o, h, l, c):
    rng = h - l; body = abs(c - o)
    return (rng - body) / max(body, 0.5), (rng - body) / max(rng, 1e-9)   # ratio (capped), fraction


def returns_to(idx, h, l, b0, fair, up, max_min):
    """minutes until price trades back through fair after bar b0 (nan if not within max_min)."""
    t0 = idx[b0]
    p = b0 + 1
    while p < len(idx):
        k = int((idx[p] - t0) / np.timedelta64(1, "m"))
        if k > max_min: break
        if (up and l[p] <= fair) or ((not up) and h[p] >= fair):
            return k
        p += 1
    return np.nan


def corr_table(rows, label):
    r = pd.DataFrame(rows, columns=["day", "which", "wb", "wf", "disp", "ret90", "ret120", "tmin"])
    n = len(r)
    if n < 30:
        print(f"\n{label}: only {n} days — too few"); return r
    y = r["ret120"].astype(float)
    pb = np.corrcoef(r["wb"], y)[0, 1]
    sp = pd.Series(r["wb"]).rank().corr(pd.Series(y).rank())
    print(f"\n=== {label}  (n={n} days) ===")
    print(f"  overall return-to-fair: within 90m {r['ret90'].mean()*100:.1f}%  within 120m {y.mean()*100:.1f}%")
    print(f"  correlation wick/body vs return(120m): point-biserial {pb:+.3f}   Spearman {sp:+.3f}")
    q = pd.qcut(r["wb"], 4, duplicates="drop")
    print(f"  {'wick/body quartile':>28}  {'n':>4}  {'ret90':>7}  {'ret120':>7}  {'med disp':>9}  {'med t(min)':>10}")
    for iv, g in r.groupby(q):
        t = g.loc[g["ret120"], "tmin"]
        print(f"  {str(iv):>28}  {len(g):>4}  {g['ret90'].mean()*100:6.1f}%  {g['ret120'].mean()*100:6.1f}%"
              f"  {g['disp'].median():8.1f}p  {t.median() if len(t) else float('nan'):>9.0f}")
    return r


def main():
    nas = S.prep(data.load())
    idx = nas.index.values.astype("datetime64[m]")
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    tod = nas["tod"].values
    news = red_news_days()

    # ---------- Q1: the opening candle (9:30, or 8:30 on red-news days) ----------
    rows = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        is_news = pd.Timestamp(day).normalize() in news
        ref_min = NEWS_MIN if is_news else NY_OPEN
        pos = gi[t == ref_min]
        prev = gi[t == ref_min - 1]
        if len(pos) != 1 or len(prev) != 1: continue
        b0 = pos[0]; fair = c[prev[0]]
        d = np.sign(c[b0] - fair)
        if d == 0: continue
        wb, wf = wick_body(o[b0], h[b0], l[b0], c[b0])
        tm = returns_to(idx, h, l, b0, fair, d > 0, 360)
        rows.append((day, "830news" if is_news else "930", wb, wf, abs(c[b0] - fair),
                     tm <= 90 if tm == tm else False, tm <= 120 if tm == tm else False, tm))
    r1 = corr_table(rows, "OPENING candle (9:30 / 8:30-on-news) vs return to fair")
    for which, lbl in [("930", "no-news days (9:30 candle)"), ("830news", "red-news days (8:30 candle)")]:
        corr_table([x for x in rows if x[1] == which], lbl)

    # ---------- Q2: the 6pm ET reopen candle ----------
    # verify the reopen empirically: minutes 0..59 server should be (nearly) absent
    cnt = pd.Series(tod).value_counts()
    pre = sum(cnt.get(m, 0) for m in range(0, 60))
    print(f"\n[6pm verify] bars with tod 00:00-00:59: {pre} (should be ~0)  |  bars at 01:00: {cnt.get(60,0)}")
    rows2 = []; vol = []
    for day, gi in nas.groupby("date").indices.items():
        t = tod[gi]
        pos = gi[t == 60]
        if len(pos) != 1: continue
        b0 = pos[0]
        if b0 == 0: continue
        bprev = b0 - 1                                     # last bar before the break (prev session)
        fair = c[bprev]
        gap_min = int((idx[b0] - idx[bprev]) / np.timedelta64(1, "m"))
        if gap_min < 30: continue                          # not actually a reopen
        d = np.sign(c[b0] - fair)
        vol.append((h[b0]-l[b0], abs(c[b0]-o[b0]), abs(o[b0]-fair)))
        if d == 0: continue
        wb, wf = wick_body(o[b0], h[b0], l[b0], c[b0])
        tm = returns_to(idx, h, l, b0, fair, d > 0, 360)
        rows2.append((day, "6pm", wb, wf, abs(c[b0] - fair),
                      tm <= 90 if tm == tm else False, tm <= 120 if tm == tm else False, tm))
    corr_table(rows2, "6pm ET reopen candle vs return to pre-break close")
    v = np.array(vol)
    if len(v):
        rng_all = (h - l)
        print(f"\n[6pm profile] n={len(v)}  avg range {v[:,0].mean():.0f}pt (median {np.median(v[:,0]):.0f})  "
              f"avg body {v[:,1].mean():.0f}pt  avg |reopen gap| {v[:,2].mean():.0f}pt")
        print(f"              vs average 1m candle range {rng_all.mean():.0f}pt — the reopen candle is "
              f"{v[:,0].mean()/max(rng_all.mean(),1e-9):.1f}x a normal minute")


if __name__ == "__main__":
    main()
