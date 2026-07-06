"""
Edge reconnaissance on TRAIN ONLY. Goal: locate any robust, causal intraday
edge on NAS100 before committing to a strategy. No trading, just structure.

Prints:
- Overnight vs intraday (RTH open->close) return decomposition (where does drift live?)
- RTH open->close mean/median and hit rate, by year (regime stability)
- Time-of-day: mean 30-min forward return by start-minute
- Opening-range breakout base rates (does a break predict continuation?)
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiment import split_train_test

DATA = Path(__file__).resolve().parent.parent / "data" / "clean_m1_ct.parquet"
PV = 2.0  # MNQ $/pt

RTH_OPEN = 8 * 60 + 30
RTH_CLOSE = 15 * 60


def daily_frames(df):
    """Return per-day RTH open, close, prior RTH close, first-15m range, etc."""
    rows = []
    for date, day in df.groupby("date"):
        rth = day[(day["minute_of_day"] >= RTH_OPEN) &
                  (day["minute_of_day"] < RTH_CLOSE)]
        if len(rth) < 60:
            continue
        o = rth["open"].iloc[0]
        c = rth["close"].iloc[-1]
        hi = rth["high"].max(); lo = rth["low"].min()
        or15 = rth[rth["minute_of_day"] < RTH_OPEN + 15]
        rows.append(dict(date=date, rth_open=o, rth_close=c, rth_hi=hi, rth_lo=lo,
                         or_hi=or15["high"].max(), or_lo=or15["low"].min()))
    d = pd.DataFrame(rows).set_index("date").sort_index()
    d["prev_close"] = d["rth_close"].shift(1)
    d["overnight_pts"] = d["rth_open"] - d["prev_close"]      # close[t-1]->open[t]
    d["intraday_pts"] = d["rth_close"] - d["rth_open"]        # open->close (tradeable RTH)
    d["gap_up"] = d["overnight_pts"] > 0
    return d


def main():
    df = pd.read_parquet(DATA)
    train, test, cut = split_train_test(df)
    d = daily_frames(train).dropna()
    print(f"TRAIN days with RTH: {len(d)}  ({d.index.min().date()} -> {d.index.max().date()})")

    on = d["overnight_pts"]; intr = d["intraday_pts"]
    print("\n--- Overnight (prev RTH close -> RTH open) vs Intraday (RTH open->close) ---")
    print(f"Overnight: mean={on.mean():.2f}pt (${on.mean()*PV:.2f}) median={on.median():.2f} "
          f"sum={on.sum():.0f}pt  up%={100*(on>0).mean():.1f}")
    print(f"Intraday : mean={intr.mean():.2f}pt (${intr.mean()*PV:.2f}) median={intr.median():.2f} "
          f"sum={intr.sum():.0f}pt  up%={100*(intr>0).mean():.1f}")
    print("  (equity drift lives overnight if overnight sum >> intraday sum)")

    print("\n--- Intraday open->close by YEAR (regime stability) ---")
    for y, g in d.groupby(d.index.year):
        i = g["intraday_pts"]
        print(f"  {y}: n={len(g):3d} mean={i.mean():7.2f}pt sum={i.sum():8.0f} up%={100*(i>0).mean():4.1f}")

    print("\n--- Gap continuation: does overnight gap predict intraday direction? ---")
    for label, mask in [("gap UP days", d["gap_up"]), ("gap DOWN days", ~d["gap_up"])]:
        g = d[mask]["intraday_pts"]
        print(f"  {label}: n={len(g)} intraday mean={g.mean():.2f}pt up%={100*(g>0).mean():.1f}")

    print("\n--- Opening-range (first 15m) breakout continuation ---")
    # after RTH close vs OR: did close finish beyond OR in break direction?
    broke_up = d["rth_close"] > d["or_hi"]
    broke_dn = d["rth_close"] < d["or_lo"]
    print(f"  close > OR15 high: {100*broke_up.mean():.1f}% of days")
    print(f"  close < OR15 low : {100*broke_dn.mean():.1f}% of days")
    # conditional: given price is above OR high at 15m mark... need intraday path; skip

    print("\n--- Time-of-day: mean forward 30m return by entry minute (RTH) ---")
    # build minute-level forward returns on RTH bars
    rth = train[(train["minute_of_day"] >= RTH_OPEN) & (train["minute_of_day"] < RTH_CLOSE)].copy()
    rth["fwd30"] = rth.groupby("date")["close"].transform(lambda s: s.shift(-30) - s)
    tod = rth.groupby("minute_of_day")["fwd30"].mean()
    for m in range(RTH_OPEN, RTH_CLOSE, 30):
        if m in tod.index:
            print(f"  {m//60:02d}:{m%60:02d} CT: fwd30 mean={tod[m]:.3f}pt (n={ (rth['minute_of_day']==m).sum() })")


if __name__ == "__main__":
    main()
