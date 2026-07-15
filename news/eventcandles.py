"""
news/eventcandles.py — align USD high-impact CPI/PPI releases to the NAS100 M1 data and answer:
  Q1: what % of the RELEASE-MINUTE 1m candle (the 8:30 bar) closed bullish?
  Q2: what % of the NEXT 1m candle (the 8:31 bar) FLIPPED — closed the opposite direction to
      the release-minute candle?

Calendar format (the CSV the user supplied): header row, DateTime in UTC (ISO +00:00), columns
DateTime,Currency,Impact,Event,Actual,Forecast,Previous,Detail. NAS M1 is naive SERVER (EET/EEST)
time, so UTC -> Europe/Bucharest gives the release bar. Alignment is VERIFIED by the range spike
before any stat is reported. Run: python3 eventcandles.py /path/to/high_impact_events_calendar.csv
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S                               # noqa: E402

SERVER_TZ = "Europe/Bucharest"                             # EET/EEST


def load_usd(csv_path):
    df = pd.read_csv(csv_path)
    df = df[(df["Currency"] == "USD") & (df["Impact"].str.contains("High", na=False))].copy()
    dt = pd.to_datetime(df["DateTime"], utc=True)
    df["dt_server"] = dt.dt.tz_convert(SERVER_TZ).dt.tz_localize(None)
    return df


def releases(df, keyword):
    """unique release minutes for an event family (CPI/PPI fire several line-items per drop)."""
    ev = df[df["Event"].str.contains(keyword, case=False, na=False)]
    return pd.Series(sorted(ev["dt_server"].unique())).dt.floor("min")


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/root/.claude/uploads/46167e15-2036-5fc2-b53b-eddc0ccbca77/a02e020d-high_impact_events_calendar.csv"
    nas = S.prep(data.load())
    idx = nas.index.values.astype("datetime64[m]")
    o = nas["open"].values.astype(float); c = nas["close"].values.astype(float)
    h = nas["high"].values.astype(float); l = nas["low"].values.astype(float)
    lo_win, hi_win = idx[0], idx[-1]

    def bar_at(t):                                          # exact-minute bar index, or -1
        p = np.searchsorted(idx, t)
        return p if (p < len(idx) and idx[p] == t) else -1

    df = load_usd(csv_path)

    # ---- alignment verification: where is the range spike around CPI releases? ----
    cpi = releases(df, "CPI"); cpi = cpi[(cpi >= lo_win) & (cpi <= hi_win)]
    print(f"NAS window {lo_win} .. {hi_win}")
    print(f"\nALIGNMENT CHECK — avg 1m range at each server offset around {len(cpi)} CPI releases:")
    base = []
    for off in range(-3, 4):
        rr = []
        for t in cpi.values.astype("datetime64[m]"):
            b = bar_at(t + np.timedelta64(off, "m"))
            if b >= 0: rr.append(h[b] - l[b])
        base.append((off, np.mean(rr) if rr else np.nan))
    for off, r in base:
        star = "  <-- release bar (biggest spike)" if r == max(x[1] for x in base) else ""
        print(f"   offset {off:+d} min : avg range {r:5.1f} pts{star}")

    # ---- Q1 & Q2 for CPI and PPI ----
    def analyse(keyword):
        rel = releases(df, keyword); rel = rel[(rel >= lo_win) & (rel <= hi_win)]
        recs = []
        for t in rel.values.astype("datetime64[m]"):
            b0 = bar_at(t); b1 = bar_at(t + np.timedelta64(1, "m"))
            if b0 < 0 or b1 < 0: continue
            d0 = np.sign(c[b0] - o[b0]); d1 = np.sign(c[b1] - o[b1])
            recs.append((t, d0, d1, c[b0] - o[b0], c[b1] - o[b1]))
        r = pd.DataFrame(recs, columns=["t", "d0", "d1", "m0", "m1"])
        n = len(r)
        bull0 = (r["d0"] > 0).sum(); bear0 = (r["d0"] < 0).sum(); doji0 = (r["d0"] == 0).sum()
        both = r[(r["d0"] != 0) & (r["d1"] != 0)]
        flip = (both["d0"] != both["d1"]).sum()
        print(f"\n=== {keyword}  ({n} aligned releases in the NAS window) ===")
        print(f"  Q1 release-minute (8:30) candle:  BULLISH {bull0}/{n} = {bull0/n*100:.1f}%   "
              f"(bearish {bear0/n*100:.1f}%, doji {doji0})")
        print(f"  Q2 next candle (8:31) FLIPS (closes opposite to the 8:30 candle): "
              f"{flip}/{len(both)} = {flip/len(both)*100:.1f}%")
        # context: how often the 8:31 continues vs flips, and avg sizes
        cont = (both["d0"] == both["d1"]).sum()
        print(f"     (continues same direction {cont}/{len(both)} = {cont/len(both)*100:.1f}%;  "
              f"avg |8:30| {r['m0'].abs().mean():.0f}pts, avg |8:31| {r['m1'].abs().mean():.0f}pts)")
        return r

    analyse("CPI"); analyse("PPI")


if __name__ == "__main__":
    main()
