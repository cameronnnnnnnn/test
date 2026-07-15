"""
news/allevents.py — for EVERY high-impact USD event: % of the RELEASE-minute 1m candle that
closed bullish/bearish, and % of the NEXT 1m candle bullish/bearish. Then pool everything for the
base rate: "if a high-impact USD event drops, what are the odds the release candle (and the next
candle) is green?"  Each event is aligned by its OWN release time (ISM 10:00, FOMC 14:00, NFP 8:30
...), converted UTC->server, exact-minute matched to the NAS M1 bar.
Run: python3 allevents.py [calendar.csv]
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S                               # noqa: E402
from eventcandles import load_usd                          # noqa: E402


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/root/.claude/uploads/46167e15-2036-5fc2-b53b-eddc0ccbca77/a02e020d-high_impact_events_calendar.csv"
    nas = S.prep(data.load())
    idx = nas.index.values.astype("datetime64[m]")
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    lo_win, hi_win = idx[0], idx[-1]

    def bar_at(t):
        p = np.searchsorted(idx, t)
        return p if (p < len(idx) and idx[p] == t) else -1

    df = load_usd(csv_path)
    df["ts"] = df["dt_server"].dt.floor("min")
    df = df[(df["ts"] >= pd.Timestamp(lo_win)) & (df["ts"] <= pd.Timestamp(hi_win))]
    df["has_actual"] = df["Actual"].notna() & (df["Actual"].astype(str).str.strip() != "")

    def candle_dirs(ts_array):
        """return (n, rel_bull, rel_bear, nxt_bull, nxt_bear, mean_rel_range) for aligned minutes."""
        rb = rr = nb = nr = 0; rng = []; n = 0
        for t in pd.unique(ts_array):
            t = np.datetime64(pd.Timestamp(t), "m")
            b0 = bar_at(t); b1 = bar_at(t + np.timedelta64(1, "m"))
            if b0 < 0 or b1 < 0: continue
            n += 1; rng.append(h[b0] - l[b0])
            d0 = c[b0] - o[b0]; d1 = c[b1] - o[b1]
            rb += d0 > 0; rr += d0 < 0; nb += d1 > 0; nr += d1 < 0
        return n, rb, rr, nb, nr, (np.mean(rng) if rng else 0.0)

    # ---- per-event table ----
    rows = []
    for ev, g in df.groupby("Event"):
        n, rb, rr, nb, nr, mr = candle_dirs(g["ts"].values)
        if n >= 5:
            rows.append((ev, n, rb / n * 100, rr / n * 100, nb / n * 100, nr / n * 100, mr))
    rows.sort(key=lambda x: -x[1])
    print(f"NAS window {str(lo_win)[:10]} .. {str(hi_win)[:10]}   (USD high-impact events, n>=5 shown)\n")
    print(f"{'event':32}{'n':>4}   {'RELEASE bull/bear':>19}   {'NEXT 1m bull/bear':>19}  {'avg|rng|':>8}")
    print("-" * 90)
    for ev, n, rbp, rrp, nbp, nrp, mr in rows:
        print(f"{ev[:32]:32}{n:>4}   {rbp:6.1f}% /{rrp:6.1f}%    {nbp:6.1f}% /{nrp:6.1f}%   {mr:6.0f}")

    # ---- aggregates ----
    def agg(sub, label):
        n, rb, rr, nb, nr, mr = candle_dirs(sub["ts"].values)   # dedup by unique release minute
        print(f"\n{label}  (n = {n} unique release minutes)")
        print(f"   RELEASE candle : BULLISH {rb/n*100:5.1f}%   BEARISH {rr/n*100:5.1f}%   (doji {(n-rb-rr)})")
        print(f"   NEXT 1m candle : BULLISH {nb/n*100:5.1f}%   BEARISH {nr/n*100:5.1f}%   (doji {(n-nb-nr)})")
        return n, rb, rr, nb, nr

    print("\n" + "=" * 90)
    print("AGGREGATE — the base rate you asked for")
    print("=" * 90)
    # literal 'any single event' (each event line-item counted; simultaneous releases share a candle)
    ne, rbe, rre, nbe, nre, _ = candle_dirs(df["ts"].values)   # NOTE: candle_dirs dedups minutes
    # so compute the line-item-weighted version explicitly:
    li = df.dropna(subset=["ts"]).copy()
    liv = [(bar_at(np.datetime64(pd.Timestamp(t), "m")),
            bar_at(np.datetime64(pd.Timestamp(t), "m") + np.timedelta64(1, "m"))) for t in li["ts"]]
    liv = [(a, b) for a, b in liv if a >= 0 and b >= 0]
    lrb = sum(c[a] > o[a] for a, b in liv); lrr = sum(c[a] < o[a] for a, b in liv)
    lnb = sum(c[b] > o[b] for a, b in liv); lnr = sum(c[b] < o[b] for a, b in liv)
    N = len(liv)
    print(f"\nEvery event line-item (n={N}; simultaneous releases share their candle):")
    print(f"   RELEASE candle : BULLISH {lrb/N*100:5.1f}%   BEARISH {lrr/N*100:5.1f}%")
    print(f"   NEXT 1m candle : BULLISH {lnb/N*100:5.1f}%   BEARISH {lnr/N*100:5.1f}%")
    agg(df, "Every unique release MINUTE (deduped — the cleaner base rate)")
    agg(df[df["has_actual"]], "Scheduled DATA releases only (numeric Actual, deduped)")


if __name__ == "__main__":
    main()
