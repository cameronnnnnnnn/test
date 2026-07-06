"""
Topstep 50K Trading Combine — Monte-Carlo challenge simulator.

Rules encoded (confirmed Phase 0):
- Start balance 50,000. Profit target +3,000 (pass at 53,000).
- Max Loss Limit: 2,000 TRAILING off END-OF-DAY balance. Never moves down.
  Locks permanently at 50,000 once EOD balance has reached >=52,000.
  Formula: MLL = min(running_max_eod_balance - 2000, 50000)   [non-decreasing]
- BREACH check is INTRADAY, real-time equity (incl. open PnL): if intraday equity
  ever <= MLL -> fail (liquidation). Default; 'eod' breach mode also supported.
- Min trading days: 2.
- Consistency: best single winning day <= 50% of total profit. Gates the PASS
  (does not fail the account); you must keep trading until satisfied. Dilutable.

A "day outcome" fed to the sim is (pnl_close, day_min_offset):
  pnl_close      = realized P&L at the day's flat-by close (can be +/-)
  day_min_offset = lowest intraday equity excursion vs the day's START balance
                   (<= min(0, pnl_close)); used for the intraday breach test.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class ComboConfig:
    start_balance: float = 50_000.0
    profit_target: float = 3_000.0
    max_loss: float = 2_000.0
    min_days: int = 2
    consistency: float = 0.50      # best day <= 50% of total profit
    lock_at_start: bool = True     # MLL caps/locks at start_balance
    breach: str = "intraday"       # 'intraday' or 'eod'
    max_days: int | None = None    # optional hard cap on days (None = unlimited)


def simulate_challenge(pnl_close, day_min_offset, cfg: ComboConfig):
    """Run one challenge over a given contiguous sequence of day outcomes.
    Returns dict: passed(bool), failed(bool), days(int), final_balance, reason.
    If it neither passes nor fails within the supplied days -> passed=failed=False
    (ran out of data / hit max_days)."""
    bal = cfg.start_balance
    peak_eod = cfg.start_balance
    mll = cfg.start_balance - cfg.max_loss
    best_day = 0.0
    n = len(pnl_close)
    for i in range(n):
        day_start_bal = bal
        # --- intraday breach test (equity low vs current MLL) ---
        eq_low = day_start_bal + day_min_offset[i]
        if cfg.breach == "intraday" and eq_low <= mll:
            return dict(passed=False, failed=True, days=i + 1,
                        final_balance=eq_low, reason="intraday_mll_breach")
        # --- settle the day ---
        bal = day_start_bal + pnl_close[i]
        if cfg.breach == "eod" and bal <= mll:
            return dict(passed=False, failed=True, days=i + 1,
                        final_balance=bal, reason="eod_mll_breach")
        if pnl_close[i] > best_day:
            best_day = pnl_close[i]
        # --- trail MLL on EOD balance (never down; lock/cap at start) ---
        peak_eod = max(peak_eod, bal)
        mll = peak_eod - cfg.max_loss
        if cfg.lock_at_start:
            mll = min(mll, cfg.start_balance)
        # --- pass test ---
        total_profit = bal - cfg.start_balance
        days = i + 1
        target_ok = total_profit >= cfg.profit_target
        days_ok = days >= cfg.min_days
        consist_ok = (best_day <= cfg.consistency * total_profit) if total_profit > 0 else False
        if target_ok and days_ok and consist_ok:
            return dict(passed=True, failed=False, days=days,
                        final_balance=bal, reason="passed")
        if cfg.max_days is not None and days >= cfg.max_days:
            return dict(passed=False, failed=False, days=days,
                        final_balance=bal, reason="max_days_no_pass")
    return dict(passed=False, failed=False, days=n,
                final_balance=bal, reason="ran_out_of_data")


# ----------------------------- Monte Carlo -----------------------------------

def mc_contiguous(pnl_close, day_min_offset, cfg, n_paths, max_len, rng):
    """Contiguous-calendar MC: pick a random start day, walk forward up to
    max_len days. Most realistic (a real challenge is ONE contiguous stretch)."""
    N = len(pnl_close)
    res = []
    for _ in range(n_paths):
        s = rng.integers(0, N)
        e = min(s + max_len, N)
        res.append(simulate_challenge(pnl_close[s:e], day_min_offset[s:e], cfg))
    return res


def mc_block_bootstrap(pnl_close, day_min_offset, cfg, n_paths, max_len, rng,
                       block=20):
    """Stationary block bootstrap: stitch random contiguous blocks (mean length
    `block`) to build each synthetic path. Preserves short-run regime clustering
    while allowing more path diversity than pure contiguous sampling."""
    N = len(pnl_close)
    res = []
    for _ in range(n_paths):
        pc, dm = [], []
        while len(pc) < max_len:
            s = rng.integers(0, N)
            L = rng.geometric(1.0 / block)
            e = min(s + L, N)
            pc.extend(pnl_close[s:e]); dm.extend(day_min_offset[s:e])
        res.append(simulate_challenge(np.array(pc[:max_len]),
                                      np.array(dm[:max_len]), cfg))
    return res


def summarize(results):
    n = len(results)
    passed = sum(r["passed"] for r in results)
    failed = sum(r["failed"] for r in results)
    neither = n - passed - failed
    days_to_pass = np.array([r["days"] for r in results if r["passed"]])
    return dict(
        n=n,
        pass_pct=100 * passed / n,
        blowup_pct=100 * failed / n,
        neither_pct=100 * neither / n,
        median_days_to_pass=float(np.median(days_to_pass)) if len(days_to_pass) else float("nan"),
        p90_days_to_pass=float(np.percentile(days_to_pass, 90)) if len(days_to_pass) else float("nan"),
    )


# ----------------------------- Validation ------------------------------------

def _validate():
    cfg = ComboConfig()
    # Case 1: clean pass on day 2 (balanced days satisfy consistency exactly)
    r = simulate_challenge(np.array([1500., 1500.]), np.array([-100., -50.]), cfg)
    assert r["passed"] and r["days"] == 2, r
    # Case 1b: target hit but consistency blocks (best day > 50% of total)
    r = simulate_challenge(np.array([2000., 1200.]), np.array([-100., -50.]), cfg)
    assert not r["passed"] and not r["failed"], r  # neither: needs more trading
    # Case 2: intraday breach despite positive close
    r = simulate_challenge(np.array([100.]), np.array([-2100.]), cfg)
    assert r["failed"] and r["reason"] == "intraday_mll_breach", r
    # Case 3: MLL locks at 50k; a later dip to 50,200 survives (would breach if
    # MLL had trailed to peak-2000=50,500 without the lock cap).
    r = simulate_challenge(np.array([2500., -400., 1500.]),
                           np.array([-100., -1900., -50.]), cfg)
    # day3 start bal = 52100, min offset -50 -> eq_low 52050 > 50000 ok;
    # EOD 53600 total 3600 best 2500 -> 2500 <= 1800? no -> not passed yet
    assert not r["failed"], r
    # verify the lock explicitly with a crafted dip
    r2 = simulate_challenge(np.array([2500., -2300.]),
                            np.array([-100., -2300.]), cfg)
    # day2 start 52500, eq_low 50200 > locked MLL 50000 -> survives (no breach)
    assert not r2["failed"], r2
    # and without lock it WOULD breach (MLL would be 50500)
    cfg_nolock = ComboConfig(lock_at_start=False)
    r3 = simulate_challenge(np.array([2500., -2300.]),
                            np.array([-100., -400.]), cfg_nolock)
    # day2 start 52500 eq_low 52100... need a dip below 50500: use -2100 offset
    r3 = simulate_challenge(np.array([2500., 0.]),
                            np.array([-100., -2100.]), cfg_nolock)
    # day2 eq_low = 52500-2100 = 50400 <= 50500 -> breach when NOT locked
    assert r3["failed"], r3
    print("[validate] all hand-worked simulator cases PASS")


if __name__ == "__main__":
    _validate()
