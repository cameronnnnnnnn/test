"""
news/newsbank.py — align the ForexFactory calendar (from ForexFactoryScraper's
forex_factory_catalog.csv) to the NAS100 M1 backtest data, and answer questions like
"what % of CPI releases were bullish for NAS" (overall and split by whether the number
beat/missed forecast).

The scraper writes HEADERLESS rows: [datetime(EST tz-aware), currency, impact, event,
actual, forecast, previous]. The NAS M1 data is naive SERVER time (EET/EEST). An 8:30 ET
release lands ~15:30 server year-round (US & EU shift together), so alignment is stable.

USAGE
  python3 newsbank.py /path/to/forex_factory_catalog.csv                 # summary of the big events
  python3 newsbank.py /path/to/forex_factory_catalog.csv "CPI m/m"       # one event, detailed
Then from Python: from newsbank import Bank; b = Bank("...csv"); b.reaction("CPI", horizon=30)
"""
import os, sys, re
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
if V4 not in sys.path: sys.path.insert(0, V4)
import data, strategies as S                               # noqa: E402

SERVER_TZ = "Europe/Bucharest"                             # EET/EEST = the FTMO/backtest server clock
HORIZONS = (5, 15, 30, 60)                                 # minutes after the release to measure
COLS = ["dt", "currency", "impact", "event", "actual", "forecast", "previous"]


def _num(x):
    """'3.7%' -> 3.7 ; '236K' -> 236000 ; '5.25%' -> 5.25 ; '' -> nan."""
    if not isinstance(x, str) or x.strip() in ("", "-"): return np.nan
    s = x.strip().replace(",", ""); mult = 1.0
    if s and s[-1] in "KkMmBbTt%":
        u = s[-1].lower(); s = s[:-1]
        mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "%": 1.0}[u]
    try: return float(s) * mult
    except ValueError: return np.nan


class Bank:
    def __init__(self, csv_path, nas=None):
        self.cal = self._load_calendar(csv_path)
        nas = nas if nas is not None else S.prep(data.load())
        self.nas_idx = nas.index.values.astype("datetime64[s]")   # naive server datetimes, sorted
        self.nas_close = nas["close"].values.astype(float)
        self._attach_reactions()

    def _load_calendar(self, p):
        df = pd.read_csv(p, header=None, names=COLS, dtype=str, keep_default_na=False)
        # datetime is tz-aware EST/EDT (offset embedded); convert to naive SERVER wall time
        dt = pd.to_datetime(df["dt"], utc=True, errors="coerce")
        df["dt_server"] = dt.dt.tz_convert(SERVER_TZ).dt.tz_localize(None)
        df = df.dropna(subset=["dt_server"]).reset_index(drop=True)
        df["impact"] = df["impact"].str.replace(" Impact Expected", "", regex=False).str.strip()
        for c in ("actual", "forecast", "previous"):
            df[c + "_n"] = df[c].map(_num)
        df["surprise"] = df["actual_n"] - df["forecast_n"]        # +ve = beat forecast
        return df

    def _price_at(self, when):
        """close of the last NAS bar at/before `when` (np.datetime64 array-safe)."""
        j = np.searchsorted(self.nas_idx, when, side="right") - 1
        return np.where(j >= 0, self.nas_close[np.clip(j, 0, len(self.nas_close) - 1)], np.nan)

    def _attach_reactions(self):
        t = self.cal["dt_server"].values.astype("datetime64[s]")
        base = self._price_at(t)
        # only events whose release falls inside the NAS data window & session (base found & fresh)
        in_win = (t >= self.nas_idx[0]) & (t <= self.nas_idx[-1])
        self.cal["px0"] = np.where(in_win, base, np.nan)
        for h in HORIZONS:
            px = self._price_at(t + np.timedelta64(h, "m"))
            self.cal[f"ret{h}"] = np.where(in_win, px - self.cal["px0"], np.nan)      # points
            self.cal[f"retp{h}"] = self.cal[f"ret{h}"] / self.cal["px0"] * 100.0      # percent

    def reaction(self, event_query, currency="USD", impact="High", horizon=30, by_surprise=True):
        m = (self.cal["event"].str.contains(event_query, case=False, na=False)
             & self.cal[f"ret{horizon}"].notna())
        if currency: m &= self.cal["currency"].eq(currency)
        if impact:   m &= self.cal["impact"].eq(impact)
        g = self.cal[m]
        r = g[f"ret{horizon}"]; rp = g[f"retp{horizon}"]
        if len(g) == 0:
            print(f"no aligned '{event_query}' events found (check currency/impact/date window)"); return g
        print(f"\n{event_query!r}  [{currency} {impact}]  {horizon}min reaction  —  {len(g)} releases "
              f"({g['dt_server'].dt.date.min()} → {g['dt_server'].dt.date.max()})")
        print(f"  BULLISH {(r>0).mean()*100:5.1f}%   mean {rp.mean():+.2f}%  median {rp.median():+.2f}%  "
              f"|move| {rp.abs().mean():.2f}%   (mean {r.mean():+.0f}pts, avg |move| {r.abs().mean():.0f}pts)")
        if by_surprise and g["surprise"].notna().any():
            for lbl, sub in [("HOT  (actual > forecast)", g[g["surprise"] > 0]),
                             ("MISS (actual < forecast)", g[g["surprise"] < 0]),
                             ("INLINE (=forecast)",       g[g["surprise"] == 0])]:
                if len(sub):
                    print(f"    {lbl:26} n={len(sub):3d}  bull {(sub[f'ret{horizon}']>0).mean()*100:5.1f}%  "
                          f"mean {sub[f'retp{horizon}'].mean():+.2f}%")
        return g

    def summary(self, events=("CPI m/m", "Core CPI m/m", "Non-Farm Employment Change",
                              "Federal Funds Rate", "PPI m/m", "Core Retail Sales m/m",
                              "Unemployment Rate", "ISM"), horizon=30):
        print("=" * 78)
        print(f"USD High-impact reaction summary — {horizon}min move on NAS100 (bullish% | mean%)")
        print("=" * 78)
        for e in events:
            self.reaction(e, horizon=horizon, by_surprise=False)


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    b = Bank(sys.argv[1])
    print(f"loaded {len(b.cal)} calendar rows; {b.cal['px0'].notna().sum()} align to the NAS window "
          f"({str(b.nas_idx[0])[:10]} → {str(b.nas_idx[-1])[:10]})")
    if len(sys.argv) >= 3:
        for h in HORIZONS: b.reaction(sys.argv[2], horizon=h)
    else:
        b.summary()


if __name__ == "__main__":
    main()
