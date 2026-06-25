#!/usr/bin/env python3
"""
Conditional risk-of-ruin from the CURRENT live state (not a fresh $15k account).

Context: the live FTMO $15k 1-step is 6 trades / 3 sessions in, sitting at
$14,249.73 (-5.00%) with ZERO winning days banked and $749.73 (= ~4R) of cushion
left to the static $13,500 fail floor. The published MC tables in NAS100_FINDINGS.md
are UNCONDITIONAL (fresh $15k). This script asks the only question that matters now:

    given where the account actually is, what is P(pass), P(blow up), P(time out),
    and how much do the deployed dials (2 sessions/day, 1.25% risk) cost vs the
    validated 1-trade/day playbook?

Edge model is calibrated to the documented backtest stats so it is not a free
parameter:
    win rate  w   = 0.31
    expectancy    = +0.128 R/trade
    profit factor = ~1.21
    breakeven move at +1R, hard take-profit at +3R (EA: TakeProfitR=3.0)

Calibration (see derivation in mc_conditional_ruin notes / commit message):
    P(-1R full stop)      = 0.595
    P( 0R breakeven)      = 0.095
    P(+uniform(0,3) trail)= 0.140   (avg +1.5R)
    P(+3R take-profit)    = 0.171
  -> expR = 0.171*3 + 0.140*1.5 + 0 - 0.595 = +0.128, w = 0.311, PF ~ 1.21  (matches docs)

Dollar sizing follows the EA: 1R = RiskPercent% of CURRENT balance (lots float with
balance), so risk shrinks as the account bleeds — modeled faithfully.

Rules enforced (FTMO 1-step, $15k):
  - static overall floor  : FAIL the instant balance <= $13,500
  - daily loss 3%         : FAIL if same-server-day realized drawdown >= 3% of the
                            day's starting balance (both 15:00 & 16:00 sessions share
                            one server day)
  - profit target         : PASS at balance >= $16,500 with >= 4 distinct trading days
  - no Friday entries / EOD-flat handled by the day loop (Fri skipped)
"""
import numpy as np

START_BAL   = 15000.0
FLOOR       = 13500.0          # static 10% floor (FTMO true rule)
TARGET      = 16500.0          # +10%
DAILY_LOSS  = 0.03             # 3% of day-start balance
MIN_DAYS    = 4

# --- calibrated per-trade R outcome sampler -------------------------------------
def sample_R(n, rng):
    u = rng.random(n)
    R = np.empty(n)
    # cumulative: [-1R .595][0R .095][trail .140][+3R .171]
    R[u < 0.595] = -1.0
    m = (u >= 0.595) & (u < 0.690); R[m] = 0.0
    m = (u >= 0.690) & (u < 0.830); R[m] = rng.uniform(0.0, 3.0, m.sum())
    R[u >= 0.830] = 3.0
    return R

def run(n_paths, start_bal, risk_pct, trades_per_day, horizon_days,
        slip_R=0.04, within_day_rho=0.0, seed=0):
    """
    slip_R         : extra loss on a full stop from slippage (live shows ~0.04R, i.e.
                     -1.00R fills as ~-1.04R). Applied to the -1R bucket only.
    within_day_rho : prob the 2nd session of a day copies the 1st session's outcome
                     class (clusters good/bad days, as the live tape did on 06-24).
    """
    rng = np.random.default_rng(seed)
    bal = np.full(n_paths, start_bal)
    alive = np.ones(n_paths, bool)
    passed = np.zeros(n_paths, bool)
    tdays = np.zeros(n_paths, int)          # distinct trading days with >=1 trade

    for d in range(horizon_days):
        day_start = bal.copy()
        day_real = np.zeros(n_paths)        # realized $ pnl so far this day
        took_trade = np.zeros(n_paths, bool)

        first_R = None
        for s in range(trades_per_day):
            act = alive & ~passed
            if not act.any():
                break
            R = sample_R(n_paths, rng)
            if s == 0:
                first_R = R.copy()
            elif within_day_rho > 0:
                copy = rng.random(n_paths) < within_day_rho
                R[copy] = first_R[copy]
            # slippage worsens full stops
            R[R == -1.0] -= slip_R

            r_dollar = bal * (risk_pct / 100.0)
            pnl = R * r_dollar
            bal = np.where(act, bal + pnl, bal)
            day_real = np.where(act, day_real + pnl, day_real)
            took_trade |= act

            # overall floor (checked every close, incl. floating ~ realized here)
            dead = act & (bal <= FLOOR)
            alive &= ~dead
            # daily 3% loss
            dbreach = act & (day_real <= -DAILY_LOSS * day_start)
            alive &= ~dbreach

        tdays += took_trade.astype(int)
        # pass check at day end
        win = alive & ~passed & (bal >= TARGET) & (tdays >= MIN_DAYS)
        passed |= win

    blew = (~alive)
    timeout = alive & ~passed
    return passed.mean(), blew.mean(), timeout.mean(), bal

def line(label, p, b, t):
    print(f"  {label:<34} pass {p*100:5.1f}%   blow-up {b*100:5.1f}%   timeout {t*100:5.1f}%")

if __name__ == "__main__":
    N = 60000
    # ~5 trading days/week; horizons in trading days
    H8, H24 = 40, 120

    print("="*78)
    print("CONDITIONAL risk-of-ruin from the CURRENT live state ($14,249.73, 0 wins)")
    print("  static floor $13,500 (cushion $749.73 = ~4R) | target $16,500")
    print("="*78)

    for H, name in [(H8, "8 weeks"), (H24, "24 weeks")]:
        print(f"\n--- horizon {name} ({H} trading days), independent sessions ---")
        line("LIVE: 2 sess/day @1.25%",
             *run(N, 14249.73, 1.25, 2, H, seed=1)[:3])
        line("playbook: 1 sess/day @1.25%",
             *run(N, 14249.73, 1.25, 1, H, seed=2)[:3])
        line("de-risk: 2 sess/day @1.00%",
             *run(N, 14249.73, 1.00, 2, H, seed=3)[:3])
        line("de-risk: 1 sess/day @1.00%",
             *run(N, 14249.73, 1.00, 1, H, seed=4)[:3])

    print("\n--- clustered bad days (within-day rho=0.5), 24 weeks ---")
    line("LIVE: 2 sess/day @1.25%, rho .5",
         *run(N, 14249.73, 1.25, 2, H24, within_day_rho=0.5, seed=5)[:3])
    line("de-risk: 2 sess/day @1.00%, rho .5",
         *run(N, 14249.73, 1.00, 2, H24, within_day_rho=0.5, seed=6)[:3])

    print("\n--- for reference: a FRESH $15k account (unconditional), 24 weeks ---")
    line("fresh: 2 sess/day @1.25%",
         *run(N, 15000.0, 1.25, 2, H24, seed=7)[:3])
    line("fresh: 1 sess/day @1.25%",
         *run(N, 15000.0, 1.25, 1, H24, seed=8)[:3])
    print("\n(compare 'fresh' blow-up to NAS100_FINDINGS r=1.25% ~ interpolated 1.0/1.5%)")
