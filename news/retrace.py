"""
news/retrace.py — after a high-impact USD release, does price come BACK to the pre-news price?
  P0 = close of the T-1 candle (T = release minute).  dir = sign(close[T] - P0) (which way the
  release pushed).  RETURN = a later bar trades back through P0 (low<=P0 if it went up, high>=P0
  if it went down).  We record minutes-to-first-return, searching bar-by-bar after the release.
Reports the return rate and the 15/30/60/120-min buckets, for all events and for events where the
release actually displaced price (>=20pts), since a tiny move "returns" trivially.
Run: python3 retrace.py [calendar.csv]
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S                               # noqa: E402
from eventcandles import load_usd                          # noqa: E402

MAX_MIN = 360                                              # search up to 6h for a return


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/root/.claude/uploads/46167e15-2036-5fc2-b53b-eddc0ccbca77/a02e020d-high_impact_events_calendar.csv"
    nas = S.prep(data.load())
    idx = nas.index.values.astype("datetime64[m]")
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    lo, hi = idx[0], idx[-1]

    def bar_at(t):
        p = np.searchsorted(idx, t)
        return p if (p < len(idx) and idx[p] == t) else -1

    df = load_usd(csv_path)
    df["ts"] = df["dt_server"].dt.floor("min")
    df = df[(df["ts"] >= pd.Timestamp(lo)) & (df["ts"] <= pd.Timestamp(hi))]

    recs = []
    for t in pd.unique(df["ts"].values):
        t = np.datetime64(pd.Timestamp(t), "m")
        b0 = bar_at(t); bm1 = bar_at(t - np.timedelta64(1, "m"))
        if b0 < 0 or bm1 < 0: continue
        P0 = c[bm1]; dr = np.sign(c[b0] - P0)
        if dr == 0: continue
        disp = abs(c[b0] - P0)
        ret_min = np.nan
        p = b0 + 1
        while p < len(idx):
            k = int((idx[p] - t) / np.timedelta64(1, "m"))
            if k > MAX_MIN: break
            if (dr > 0 and l[p] <= P0) or (dr < 0 and h[p] >= P0):
                ret_min = k; break
            p += 1
        recs.append((disp, ret_min))
    r = pd.DataFrame(recs, columns=["disp", "ret_min"])

    def report(sub, label):
        n = len(sub); rm = sub["ret_min"]
        def pct(mx): return (rm <= mx).sum() / n * 100
        print(f"\n{label}  (n={n};  median release displacement {sub['disp'].median():.0f}pts)")
        print(f"  RETURNS to pre-news price:  within 2h {pct(120):5.1f}%   within 6h {rm.notna().mean()*100:5.1f}%   "
              f"never(6h) {rm.isna().mean()*100:4.1f}%")
        print(f"  cumulative (% of ALL {label.split()[0].lower()} events):  "
              f"<=15m {pct(15):4.1f}%   <=30m {pct(30):4.1f}%   <=1h {pct(60):4.1f}%   <=2h {pct(120):4.1f}%")
        ret = sub[rm <= 120]
        if len(ret):
            rr = ret["ret_min"]
            print(f"  of the ones that DO return (within 2h, n={len(ret)}):  "
                  f"<=15m {(rr<=15).mean()*100:4.1f}%   <=30m {(rr<=30).mean()*100:4.1f}%   "
                  f"<=1h {(rr<=60).mean()*100:4.1f}%   (median {rr.median():.0f}min)")

    report(r, "ALL releases")
    report(r[r["disp"] >= 20], "MEANINGFUL (>=20pt push) releases")
    report(r[r["disp"] >= 40], "BIG (>=40pt push) releases")


if __name__ == "__main__":
    main()
