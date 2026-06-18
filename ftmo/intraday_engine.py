"""
Intraday backtest engine on real EURUSD M1 (2021-2025).

Honest fill model:
  - Signals on resampled bars (e.g. 15m), decided at bar close.
  - Enter at NEXT bar open + half the real per-bar spread (cost paid both ways).
  - Stop / target checked bar-by-bar via that bar's HIGH/LOW. If both touched in
    one bar, assume STOP first (conservative).
  - One position at a time. Flat by session end each day (no overnight/weekend).
  - Per-trade Max Adverse Excursion (MAE) recorded so the FTMO intraday daily-loss
    rule can be enforced on the real worst floating drawdown, not just closes.

All trade results expressed as R-multiples (P&L / risk) -> currency-agnostic,
feeds the FTMO simulator + Monte Carlo unchanged.
"""
import pandas as pd, numpy as np

PIP = 0.0001
PT  = 0.00001   # 5-digit point; spread column is in points

def load_m1():
    return pd.read_pickle("ftmo/m1/eurusd_m1.pkl")

def resample(m1, tf="15min"):
    s = m1.set_index("dt")
    o = s["open"].resample(tf).first()
    h = s["high"].resample(tf).max()
    l = s["low"].resample(tf).min()
    c = s["close"].resample(tf).last()
    sp = s["spread"].resample(tf).mean()
    bars = pd.DataFrame({"open":o,"high":h,"low":l,"close":c,"spread":sp}).dropna()
    bars["date"] = bars.index.date
    bars["hour"] = bars.index.hour
    bars["minute"] = bars.index.minute
    bars["dow"] = bars.index.dayofweek
    return bars.reset_index().rename(columns={"index":"dt"})

def backtest(bars, signal_fn, stop_pips, target_R,
             session=(7, 20), flat_hour=20, slip_pips=0.2, max_trades_day=None):
    """
    signal_fn(bars) -> array in {-1,0,+1}, decision valid at close of that bar.
    stop_pips: stop distance in pips. target = target_R * stop.
    session: (start_hour, end_hour) server time during which NEW entries allowed.
    flat_hour: force flat at/after this server hour.
    Returns trades DataFrame with R, date, MAE_R, dir, dt.
    """
    sig = signal_fn(bars)
    o = bars["open"].values; h = bars["high"].values
    l = bars["low"].values;  c = bars["close"].values
    spread = bars["spread"].values * PT
    hour = bars["hour"].values
    day = bars["date"].values
    n = len(bars)
    stop = stop_pips * PIP
    slip = slip_pips * PIP
    trades = []
    i = 0
    cur_day = None; day_count = 0
    while i < n - 1:
        if day[i] != cur_day:
            cur_day = day[i]; day_count = 0
        s = sig[i]
        in_sess = session[0] <= hour[i] < session[1]
        ok_more = (max_trades_day is None) or (day_count < max_trades_day)
        if s == 0 or not in_sess or not ok_more:
            i += 1; continue
        # enter at next bar open + half spread (cost) in trade direction
        entry = o[i+1] + s * (spread[i+1] / 2 + slip)
        if s > 0:
            stop_px = entry - stop; tgt_px = entry + target_R * stop
        else:
            stop_px = entry + stop; tgt_px = entry - target_R * stop
        mae = 0.0  # worst adverse excursion in price (positive number)
        exitR = None
        j = i + 1
        while j < n and day[j] == cur_day:
            # adverse excursion
            adv = (entry - l[j]) if s > 0 else (h[j] - entry)
            mae = max(mae, adv)
            # stop check first (conservative), then target
            if (s > 0 and l[j] <= stop_px) or (s < 0 and h[j] >= stop_px):
                exitR = -1.0 - slip/stop  # extra slip on stop fill
                break
            if (s > 0 and h[j] >= tgt_px) or (s < 0 and l[j] <= tgt_px):
                exitR = target_R - (spread[i+1]/2 + slip)/stop
                break
            # force flat at session end
            if hour[j] >= flat_hour and j > i+1:
                px = c[j]
                exitR = (s*(px-entry) - (spread[i+1]/2 + slip)) / stop
                break
            j += 1
        if exitR is None:  # day ended while open -> close at last bar of day
            px = c[min(j, n-1)]
            exitR = (s*(px-entry) - (spread[i+1]/2 + slip)) / stop
        trades.append({"dt":bars["dt"].iloc[i+1], "date":cur_day, "dir":int(s),
                       "R":exitR, "MAE_R":mae/stop})
        day_count += 1
        i = max(j, i+1)  # no overlapping positions
    return pd.DataFrame(trades)

def trade_stats(tr):
    if len(tr)==0: return None
    R=tr["R"].values
    days=tr["date"].nunique()
    return dict(n=len(R), tpd=len(R)/days, win=(R>0).mean(), expR=R.mean(),
                pf=R[R>0].sum()/(-R[R<0].sum()+1e-9), sumR=R.sum(), days=days)
