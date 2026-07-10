"""
newstrat/allinstr.py — unified loader for ALL FIVE instruments (NAS100 + EURUSD/GBPUSD/AUDUSD/
USDJPY) so a strategy can be scanned across every market on one footing. Returns per instrument:
the prepped M1 frame, a realistic round-turn cost (index pts for NAS100; 1.5x median spread for
forex), the daily-ATR map (so stops are ATR-scaled and comparable across instruments), and the
main session opens in server minutes. Server time is EET for all of them.
"""
import os, sys
import numpy as np
V4 = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ftmo", "v4"))
CP = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "challengephaseHF"))
for p in (V4, CP):
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S                          # noqa: E402
import fx_data                                        # noqa: E402

FX = ["EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]
ALL = ["NAS100"] + FX

# candidate session opens (server minutes): Tokyo, London, US-index, US-cash
SESSIONS = {"tokyo": 0, "london": 10*60, "usidx": 16*60, "uscash": 16*60+30}


def load_all(verbose=True):
    out = {}
    nas = S.prep(data.load())
    out["NAS100"] = dict(df=nas, cost=2.0, pt=1.0)
    for x in FX:
        df = S.prep(fx_data.load(x))
        pt = 0.001 if df["close"].iloc[-1] > 50 else 0.00001
        out[x] = dict(df=df, cost=1.5 * df["spread"].median() * pt, pt=pt)
    for x in out:
        df = out[x]["df"]
        out[x]["atr"] = S.daily_atr(df, n=14)
        med = np.nanmedian([v for v in out[x]["atr"].values() if v == v])
        out[x]["atr_med"] = med
        out[x]["ndays"] = df["date"].nunique()
        if verbose:
            print(f"  {x:8} {out[x]['ndays']:4d} days  cost {out[x]['cost']:.5f}  "
                  f"med ATR {med:.5f} ({med/out[x]['pt']:.0f} pts)  "
                  f"{df.index[0].date()}..{df.index[-1].date()}")
    return out


def stopmap(info, frac):
    """ATR-scaled stop map for an instrument: {date: frac * daily_ATR} in price units."""
    return {d: frac * v for d, v in info["atr"].items() if v == v}


if __name__ == "__main__":
    print("Loading all instruments ...")
    load_all()
