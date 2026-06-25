"""
v2/engine.py — intraday M1 fill simulator with realistic costs + MAE/MFE.

A strategy emits ORDERS: (entry_bar, direction, stop_pts, exit_spec). The engine
fills each by scanning M1 bars forward until stop / take-profit / trail / EOD,
recording the net R-multiple AND the intraday max-adverse/-favourable excursion
(needed so the FTMO daily & overall limits can be checked on FLOATING equity).

Conventions
- direction: +1 long, -1 short
- stop_pts : initial 1R risk distance in index points
- cost_pts : round-turn cost (spread+commission+slippage) in points, subtracted once
- within-bar tie-break: STOP assumed hit before TP (conservative, no tick data)
- R-multiple is net of cost; a clean stop-out is about -1.0R - cost/stop
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass

@dataclass
class ExitSpec:
    tp_R: float = 0.0          # hard take-profit in R (0 = none)
    be_R: float = 0.0          # move stop to breakeven once +be_R reached (0 = none)
    trail_R: float = 0.0       # trail stop trail_R behind running extreme (0 = none)
    max_bars: int = 10_000     # force time-exit this many bars after entry (EOD)
    partial_R: float = 0.0     # scale out partial_frac of size at +partial_R (0 = none)
    partial_frac: float = 0.5  # fraction closed at the partial target; rest -> BE + trail

def simulate(df, orders, cost_pts=2.0, slip_pts=0.0):
    """
    orders: list of dicts {entry_bar, dir, stop_pts, spec: ExitSpec, tag, day}
    returns: DataFrame of trades with R, mae_R, mfe_R, reason, times.
    """
    H = df["high"].values.astype(np.float64)
    L = df["low"].values.astype(np.float64)
    C = df["close"].values.astype(np.float64)
    O = df["open"].values.astype(np.float64)
    idx = df.index
    n = len(df)
    rows = []
    for od in orders:
        b0 = od["entry_bar"]; d = od["dir"]; stop = od["stop_pts"]; spec = od["spec"]
        if b0 + 1 >= n:
            continue
        # enter at next bar open (no look-ahead) + slippage against us
        entry = O[b0 + 1] + d * slip_pts
        stop_px = entry - d * stop
        tp_px = entry + d * spec.tp_R * stop if spec.tp_R > 0 else None
        run_ext = entry           # running favourable extreme
        be_done = False
        mae = 0.0; mfe = 0.0      # in points, signed favourable = +
        part_done = False; part_R = 0.0
        pfrac = spec.partial_frac if spec.partial_R > 0 else 0.0
        last = min(b0 + 1 + spec.max_bars, n - 1)
        if od.get("eod_bar"):
            last = min(last, od["eod_bar"])
        reason = "eod"; exit_px = C[last]; exit_bar = last
        for b in range(b0 + 1, last + 1):
            hi = H[b]; lo = L[b]
            # excursions (favourable = d*(px-entry))
            fav_hi = d * (hi - entry); fav_lo = d * (lo - entry)
            mfe = max(mfe, fav_hi if d > 0 else fav_lo)
            mae = min(mae, fav_lo if d > 0 else fav_hi)
            # update running extreme for trailing
            run_ext = max(run_ext, hi) if d > 0 else min(run_ext, lo)
            # breakeven
            if spec.be_R > 0 and not be_done:
                if d * (run_ext - entry) >= spec.be_R * stop:
                    stop_px = entry; be_done = True
            # trail
            if spec.trail_R > 0:
                tstop = run_ext - d * spec.trail_R * stop
                stop_px = tstop if d > 0 and tstop > stop_px else (
                          tstop if d < 0 and tstop < stop_px else stop_px)
            # STOP first (conservative)
            if (d > 0 and lo <= stop_px) or (d < 0 and hi >= stop_px):
                exit_px = stop_px; reason = "stop"; exit_bar = b; break
            # scale-out partial: bank pfrac at +partial_R, move runner to BE
            if spec.partial_R > 0 and not part_done:
                ptp = entry + d * spec.partial_R * stop
                if (d > 0 and hi >= ptp) or (d < 0 and lo <= ptp):
                    part_R = pfrac * spec.partial_R; part_done = True
                    stop_px = max(stop_px, entry) if d > 0 else min(stop_px, entry)
            # TP (full)
            if tp_px is not None and ((d > 0 and hi >= tp_px) or (d < 0 and lo <= tp_px)):
                exit_px = tp_px; reason = "tp"; exit_bar = b; break

        runner_R = (d * (exit_px - entry)) / stop
        R = part_R + (1.0 - pfrac) * runner_R - cost_pts / stop
        rows.append(dict(
            day=od.get("day"), tag=od.get("tag", ""),
            entry_dt=idx[b0 + 1], exit_dt=idx[exit_bar], dir=d,
            entry=entry, exit=exit_px, stop_pts=stop, reason=reason,
            R=R, mae_R=mae / stop, mfe_R=mfe / stop))
    return pd.DataFrame(rows)

def trades_to_days(trades, all_days, daily_stop_R=0.0):
    """
    Aggregate trades to one row per CALENDAR (server) day:
      day_R      net R for the day
      day_min_R  worst intraday cumulative R (realized-so-far + open-trade MAE)
      day_max_R  best  intraday cumulative R
      n          number of trades
    all_days: sorted unique server dates that had >=1 *possible* trading session
              (we only emit rows for days with trades; flat days carry 0/0/0).
    """
    recs = {}
    for day, g in trades.groupby("day"):
        cum = 0.0; lo = 0.0; hi = 0.0; nt = 0
        for _, t in g.sort_values("entry_dt").iterrows():
            # daily-loss stop: once the day is down daily_stop_R, take no more trades
            if daily_stop_R > 0 and cum <= -daily_stop_R:
                break
            lo = min(lo, cum + t["mae_R"])      # dip while this trade is open
            hi = max(hi, cum + t["mfe_R"])
            cum += t["R"]
            lo = min(lo, cum); hi = max(hi, cum); nt += 1
        recs[day] = dict(day_R=cum, day_min_R=lo, day_max_R=hi, n=nt)
    out = pd.DataFrame([{"day": d, **recs[d]} for d in sorted(recs)])
    return out

def edge_stats(trades):
    """Win rate / expectancy / profit factor etc. from the real trade sequence."""
    R = trades["R"].values
    wins = R[R > 0]; losses = R[R <= 0]
    wr = len(wins) / len(R) if len(R) else 0.0
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    return dict(n=len(R), wr=wr, expR=R.mean() if len(R) else 0.0,
                pf=pf, maxR=R.max() if len(R) else 0.0,
                minR=R.min() if len(R) else 0.0,
                avg_win=wins.mean() if len(wins) else 0.0,
                avg_loss=losses.mean() if len(losses) else 0.0)
