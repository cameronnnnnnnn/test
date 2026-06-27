"""
Lucid/lucid.py — "25K FLEX EVAL" rule engine + Monte-Carlo monthly pass-rate.

RULES (from the card):
  account            $25,000
  profit target      +$1,250  (5%)      -> pass when EOD balance >= 26,250
  max loss limit     $1,000   (4%)      -> EOD TRAILING drawdown (see below)
  drawdown type      EOD      -> the floor trails the highest END-OF-DAY balance:
                        floor = max(EOD balances incl. start) - 1,000
                        (intraday peaks do NOT raise it — forgiving on the upside)
                        a BREACH is checked on the intraday LOW (floating equity):
                        if  start_of_day_balance + intraday_min$  <= floor  -> BLOW
  daily loss limit   NONE
  consistency        50%  -> best single green day <= 50% of total NET profit
                            (soft: blocks the pass until satisfied, never fails you)
  max size           2 minis OR 20 micros  -> $40 / index-point cap (NQ: $20/$2 per pt)

Dollars: a trade risks `risk_d` per 1R (= stop_pts pts).  n_micros = risk_d/(stop_pts*2),
must be <= 20 (= 2 minis).  day$ = day_R*risk_d ; intraday-min$ = day_min_R*risk_d.

We bootstrap whole trading days (day_R, day_min_R from the real backtest) into synthetic
attempts, block-sampled to keep autocorrelation.  "Monthly pass rate" = P(pass within the
deadline, default 21 trading days).
"""
import numpy as np, pandas as pd
import engine

ACCT   = 25000.0
TARGET = 1250.0
MAXDD  = 1000.0
CONSIST = 0.50
PT_MICRO = 2.0; PT_MINI = 20.0; MAX_PT = 40.0     # NQ contract $ / index point
MONTH = 21

def build_days(trades, all_dates, daily_stop_R=0.0):
    """daily_stop_R>0: self-imposed 'stop trading for the day after -X R' (no firm daily
    limit exists, but capping intraday losses reduces EOD-trailing-DD breaches)."""
    base = pd.DataFrame({"day": all_dates, "day_R": 0.0, "day_min_R": 0.0, "n": 0}).set_index("day")
    if len(trades):
        agg = engine.trades_to_days(trades, all_dates, daily_stop_R=daily_stop_R).set_index("day")
        base.loc[agg.index, ["day_R", "day_min_R", "n"]] = agg[["day_R", "day_min_R", "n"]].values
    return base.reset_index().to_records(index=False)

def run_eval_mc(days, risk_d, deadline=MONTH, n_paths=40000, seed=0, block=5,
                acct=ACCT, target=TARGET, maxdd=MAXDD, consist=CONSIST, min_days=1,
                sizing="fixed", k=0.30, rd_min=50.0, rd_max=400.0, breach="eod",
                _return_paths=False):
    """Monte-Carlo the FLEX EVAL. Returns pass/blow/timeout rates + diagnostics.
    breach='eod'     : fail only if END-OF-DAY balance <= (peak EOD - maxdd). Intraday
                       swings don't matter (matches 'EOD drawdown' + 'no daily limit').
    breach='intraday': fail if FLOATING equity touches the trailing floor (stricter).
    sizing='fixed'   : risk_d $ per 1R every day.
    sizing='buffer'  : risk_d_t = clip(k*(balance-floor), rd_min, rd_max) (anti-blow)."""
    rng = np.random.default_rng(seed)
    dR   = np.asarray(days["day_R"], float)
    dmin = np.asarray(days["day_min_R"], float)
    traded = (np.asarray(days["n"]) > 0).astype(int)
    nD = len(dR)
    nb = int(np.ceil(deadline/block))
    idx = ((rng.integers(0,nD,size=(n_paths,nb))[:,:,None]+np.arange(block)[None,None,:])
           % nD).reshape(n_paths,-1)[:,:deadline]
    Rday = dR[idx]; Rmin = dmin[idx]; Tr = traded[idx]    # raw R (sized in the loop)

    bal  = np.full(n_paths, acct)         # current (EOD) balance
    peak = np.full(n_paths, acct)         # highest EOD balance so far (trails the floor)
    mg   = np.zeros(n_paths)              # max single green day  (consistency numerator)
    dtr  = np.zeros(n_paths, int)
    passed = np.zeros(n_paths, bool); blown = np.zeros(n_paths, bool)
    tpass  = np.full(n_paths, -1, int)

    for t in range(deadline):
        live = ~passed & ~blown
        floor = peak - maxdd                              # from prior EOD peak
        rd = risk_d if sizing == "fixed" else np.clip(k*(bal-floor), rd_min, rd_max)
        if breach == "intraday":
            dead = live & (bal + Rmin[:, t]*rd <= floor)  # floating equity low touches floor
            blown |= dead; live = ~passed & ~blown
        prof = Rday[:, t]*rd
        bal = np.where(live, bal + prof, bal)             # close the day
        if breach == "eod":
            dead = live & (bal <= floor)                  # only the EOD close is judged
            blown |= dead; live = ~passed & ~blown
        gp = np.where(live & (prof > 0), prof, 0.0); mg = np.maximum(mg, gp)
        dtr += np.where(live, Tr[:, t], 0)
        peak = np.where(live, np.maximum(peak, bal), peak)
        net = bal - acct
        consistent = mg <= consist*net + 1e-9            # best day <= 50% of NET profit
        now = live & (net >= target) & (dtr >= min_days) & consistent
        tpass = np.where(now & (tpass < 0), t, tpass); passed |= now

    if _return_paths:
        return dict(passed=passed, blown=blown, tpass=tpass, idx=idx)
    return dict(pass_rate=passed.mean(), blow_rate=blown.mean(),
                timeout_rate=(~passed & ~blown).mean(),
                med_days=(np.median(tpass[passed])+1 if passed.any() else np.nan),
                p25_days=(np.percentile(tpass[passed],25)+1 if passed.any() else np.nan))

def micros_for(risk_d, stop_pts):
    """Implied micro contracts for risk_d at this stop; cap is 20 (=2 minis)."""
    return risk_d / (stop_pts * PT_MICRO)
