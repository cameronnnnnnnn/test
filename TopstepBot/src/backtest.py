"""
Intraday backtester: bars + strategy -> per-day outcomes for the Topstep sim.

Contract: MNQ micro Nasdaq-100. $2/point, tick 0.25 pt = $0.50/tick.
Costs (conservative, per contract round-turn):
  commission_rt = $1.00 ; slippage = 1 tick/side (0.25pt) -> $1.00 rt.

Rules honored here (the intraday side):
- Trades only inside the configured session window (default RTH 08:30-15:00 CT).
- Hard flat-by cutoff (default 15:10 CT = 910 min) -> no overnight/weekend risk.
- One position at a time, bracket (stop/target in points) + time exit.
- Everything CAUSAL: entry on the bar AFTER the signal bar's close.

Output per CT trading day: (pnl_close, day_min_offset) in ACCOUNT DOLLARS,
where day_min_offset is the worst intraday equity excursion vs the day's start.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

POINT_VALUE = {"MNQ": 2.0, "NQ": 20.0}
TICK = 0.25


@dataclass
class Costs:
    commission_rt: float = 1.00   # $ per contract round turn
    slippage_ticks_per_side: float = 1.0


@dataclass
class ExecConfig:
    contract: str = "MNQ"
    session_start: int = 8 * 60 + 30   # 08:30 CT
    session_end: int = 15 * 60         # 15:00 CT last entry window end
    flat_by: int = 15 * 60 + 10        # 15:10 CT forced flat
    costs: Costs = field(default_factory=Costs)


def _cost_per_contract(cfg: ExecConfig) -> float:
    pv = POINT_VALUE[cfg.contract]
    slip = cfg.costs.slippage_ticks_per_side * 2 * TICK * pv   # both sides
    return cfg.costs.commission_rt + slip


def backtest_day(bars: pd.DataFrame, signals: np.ndarray, size: np.ndarray,
                 stop_pts: float, target_pts: float, cfg: ExecConfig):
    """Simulate one day.
    bars: DataFrame with open/high/low/close, index=timestamps (CT), one day.
    signals: array len(bars); +1 long, -1 short, 0 none (acted on NEXT bar open).
    size: array len(bars); contracts to trade for that signal (>=0).
    Returns (pnl_close, day_min_offset) in dollars.
    """
    o = bars["open"].values; h = bars["high"].values
    l = bars["low"].values;  c = bars["close"].values
    mod = bars["minute_of_day"].values
    pv = POINT_VALUE[cfg.contract]
    cpc = _cost_per_contract(cfg)

    realized = 0.0
    min_offset = 0.0            # worst equity excursion vs day start
    pos = 0                     # +1/-1/0
    qty = 0
    entry = 0.0
    stop = target = 0.0
    n = len(bars)

    def mark(offset):
        nonlocal min_offset
        if offset < min_offset:
            min_offset = offset

    for i in range(n):
        # forced flat at cutoff
        if pos != 0 and mod[i] >= cfg.flat_by:
            realized += pos * (o[i] - entry) * pv * qty - cpc * qty
            pos = 0; qty = 0
        # mark intraday worst while holding (use bar extremes)
        if pos != 0:
            worst_px = l[i] if pos > 0 else h[i]
            open_mtm = pos * (worst_px - entry) * pv * qty
            mark(realized + open_mtm - cpc * qty)
            # bracket exits
            if pos > 0:
                if l[i] <= stop:
                    realized += (stop - entry) * pv * qty - cpc * qty; pos = 0; qty = 0
                elif h[i] >= target:
                    realized += (target - entry) * pv * qty - cpc * qty; pos = 0; qty = 0
            else:
                if h[i] >= stop:
                    realized += (entry - stop) * pv * qty - cpc * qty; pos = 0; qty = 0
                elif l[i] <= target:
                    realized += (entry - target) * pv * qty - cpc * qty; pos = 0; qty = 0
        else:
            mark(realized)
        # act on signal from PREVIOUS bar close -> enter at THIS bar open
        if pos == 0 and i > 0 and signals[i - 1] != 0 and size[i - 1] > 0:
            if cfg.session_start <= mod[i] < cfg.session_end and mod[i] < cfg.flat_by:
                pos = int(signals[i - 1]); qty = int(size[i - 1])
                entry = o[i]
                if pos > 0:
                    stop = entry - stop_pts; target = entry + target_pts
                else:
                    stop = entry + stop_pts; target = entry - target_pts
    # close any residual at last close
    if pos != 0:
        realized += pos * (c[-1] - entry) * pv * qty - cpc * qty
        pos = 0
    return realized, min(min_offset, realized if realized < 0 else 0.0)


def run_backtest(df: pd.DataFrame, strategy, cfg: ExecConfig):
    """df: full clean M1 (CT index). strategy: object with .signals(day_bars)->
    (signals, size, stop_pts, target_pts). Returns DataFrame indexed by date with
    pnl_close, day_min_offset, n columns."""
    rth = df[(df["minute_of_day"] >= cfg.session_start - 60) &
             (df["minute_of_day"] <= cfg.flat_by + 5)]  # small pad for context
    out = []
    for date, day in rth.groupby("date"):
        if len(day) < 30:
            continue
        sig, size, stop_pts, target_pts = strategy.signals(day)
        pnl, moff = backtest_day(day, sig, size, stop_pts, target_pts, cfg)
        out.append((date, pnl, moff))
    res = pd.DataFrame(out, columns=["date", "pnl_close", "day_min_offset"])
    res = res.set_index("date").sort_index()
    return res
