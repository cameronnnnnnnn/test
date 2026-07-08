"""
v2/ftmo.py — FTMO $15k 1-Step rule engine + Monte-Carlo pass/blow estimator.

RULES (locked with the user):
  start 15,000 ; PASS at +10% (16,500) ; min 4 trading days
  overall max loss 10% -> STATIC floor at 13,500 (equity incl. floating)
  daily  max loss  3% -> equity may not fall 3% below the day's start (incl. floating)
  consistency: best green day <= 50% of summed green-day profit (soft: delays, never fails)

Method: bootstrap whole TRADING DAYS (each summarised by day_R, day_min_R from the
real backtest) into synthetic challenge attempts. Working in units of the START
balance (1.0 = 15,000). Per-trade risk r compounds off CURRENT balance (matches the
EA's balance-based sizing). day_min_R captures the worst intraday floating point, so
the 3% daily and 10% overall limits are checked on floating equity, not just closes.
"""
import numpy as np

TARGET = 1.10
FLOOR  = 0.90      # static 10% floor
DAILY  = 0.03
MIN_DAYS = 4

def run_mc(days, risk, deadline, n_paths=40000, seed=0, block=1,
           floor_mode="static", sizing="fixed",
           risk_k=0.125, r_min=0.003, r_max=0.02, consistency=True, e0=1.0):
    """
    days: structured arrays with keys day_R, day_min_R, n (per weekday in sample).
    risk: fraction risked per trade off current balance (e.g. 0.0125).
    deadline: number of trading (week)days in the attempt window.
    block: >1 => block bootstrap (preserve autocorrelation) of contiguous days.
    returns dict of rates + diagnostics.
    """
    rng = np.random.default_rng(seed)
    dR   = np.asarray(days["day_R"], float)
    dmin = np.asarray(days["day_min_R"], float)
    traded = (np.asarray(days["n"]) > 0).astype(np.int8)
    nD = len(dR)

    # --- sample day-index matrix (n_paths, deadline) ---
    if block <= 1:
        samp = rng.integers(0, nD, size=(n_paths, deadline))
    else:
        nb = int(np.ceil(deadline / block))
        starts = rng.integers(0, nD, size=(n_paths, nb))
        offs = np.arange(block)
        samp = ((starts[:, :, None] + offs[None, None, :]) % nD).reshape(n_paths, -1)[:, :deadline]

    R_   = dR[samp]      # (P, T) net day R
    Rmin = dmin[samp]
    Tr   = traded[samp]

    E = np.full(n_paths, e0, float)      # e0<1 => start already in drawdown (conditional pass)
    days_traded = np.zeros(n_paths, int)
    sum_green = np.zeros(n_paths)
    max_green = np.zeros(n_paths)
    passed = np.zeros(n_paths, bool)
    blown  = np.zeros(n_paths, bool)
    blow_daily = np.zeros(n_paths, bool)
    t_pass = np.full(n_paths, -1, int)

    for t in range(deadline):
        live = ~passed & ~blown
        if not live.any():
            break
        rt = R_[:, t]; rmin = Rmin[:, t]
        # per-trade risk this day: fixed, or a fraction of the distance to the floor
        # (static floor => buffer grows with profit => press when ahead, ease when behind)
        if sizing == "buffer":
            rr = np.clip(risk_k * (E - FLOOR), r_min, r_max)
        else:
            rr = risk
        # intraday floating low this day
        intraday_loss_of_daystart = rmin * rr              # fraction of day-start
        E_low = E * (1.0 + rmin * rr)                      # equity at intraday low
        daily_breach   = intraday_loss_of_daystart <= -DAILY
        overall_breach = E_low <= FLOOR
        blow_now = live & (daily_breach | overall_breach)
        blown |= blow_now
        blow_daily |= (blow_now & daily_breach & ~overall_breach)

        live = ~passed & ~blown
        # close out the day for survivors
        profit = E * rt * rr                                # start-units profit today
        E = np.where(live, E * (1.0 + rt * rr), E)
        gp = np.where(live & (profit > 0), profit, 0.0)
        sum_green += gp
        max_green = np.maximum(max_green, gp)
        days_traded += np.where(live, Tr[:, t], 0)

        # pass check (target + min days + consistency)
        consistent = (max_green <= 0.5 * sum_green + 1e-12) if consistency else True
        pass_now = live & (E >= TARGET) & (days_traded >= MIN_DAYS) & consistent
        passed |= pass_now
        t_pass = np.where(pass_now & (t_pass < 0), t, t_pass)

    return dict(
        pass_rate=passed.mean(),
        blow_rate=blown.mean(),
        timeout_rate=(~passed & ~blown).mean(),
        blow_daily_share=(blow_daily.sum() / max(blown.sum(), 1)),
        med_days_to_pass=(np.median(t_pass[passed]) + 1 if passed.any() else np.nan),
        mean_days_to_pass=(t_pass[passed].mean() + 1 if passed.any() else np.nan),
        final_equity_median=np.median(E),
    )

def sweep(days, risks, deadline, **kw):
    return {r: run_mc(days, r, deadline, **kw) for r in risks}
