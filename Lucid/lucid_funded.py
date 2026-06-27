"""
Lucid/lucid_funded.py — FUNDED-phase income model for the 25K LucidFlex account, and
the head-to-head efficiency vs an FTMO 15k funded account (income per eval-dollar).

FUNDED RULES MODELED (confirmed from the card + user):
  $25,000 ; max loss $1,000, EOD-trailing that LOCKS at breakeven ($25,000) once you are
  +$1,000 (peak EOD $26,000) ; NO daily loss limit ; EOD breach.
  Split 90/10.  Payout: request up to 50% of accumulated profit, capped $1,000/request,
  minimum $500 ; eligible after >=5 trading days AND >=5 days of >=$100 profit.

ASSUMPTIONS (flagged; one-line params):
  * 5-green-days / 5-trading-days = a ONE-TIME unlock; then withdrawals on a 5-trading-day
    cadence (pay_cycle). Per-cycle green-day rules would slow payouts (tested via pay_cycle).
  * withdraw the MAX allowed each eligible cycle (lock gains in before a blow).
  * run to account death, cap 504 trading days (2y). Strategy = the verified EU-open ORB.

FTMO 15k funded baseline (from ../ftmo/v4 withdraw_phase, static $13,500 floor, 90/10):
  avg lifetime extraction to trader ~ $2,300-4,600 (right-skewed; median lower).
"""
import numpy as np
import data, strategies as S, engine, lucid

COST = 1.0
ACCT, MAXDD, SPLIT = 25000.0, 1000.0, 0.90
WD_FRAC, WD_CAP, WD_MIN = 0.50, 1000.0, 500.0
MIN_TDAYS, MIN_GREEN, GREEN_THR = 5, 5, 100.0

def funded_mc(days, risk_d, N=80000, cap=504, seed=3, block=5, pay_cycle=5, lock=True):
    rng = np.random.default_rng(seed)
    dR = np.asarray(days["day_R"], float); dmin = np.asarray(days["day_min_R"], float)
    traded = (np.asarray(days["n"])>0).astype(int); nD = len(dR)
    nb = int(np.ceil(cap/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    Rday = dR[idx]; Tr = traded[idx]

    bal = np.full(N, ACCT); peak = np.full(N, ACCT); alive = np.ones(N, bool)
    cum = np.zeros(N); npay = np.zeros(N, int); life = np.full(N, cap)
    tdays = np.zeros(N, int); greens = np.zeros(N, int); since = np.full(N, 10**6)
    for t in range(cap):
        prof = Rday[:, t]*risk_d
        bal = np.where(alive, bal + prof, bal)                       # close the day (EOD)
        floor = np.minimum(peak - MAXDD, ACCT) if lock else (peak - MAXDD)
        dead = alive & (bal <= floor)                               # EOD breach (no daily limit)
        life = np.where(dead, t, life); alive &= ~dead
        peak = np.where(alive, np.maximum(peak, bal), peak)
        tdays += np.where(alive, Tr[:, t], 0)
        greens += np.where(alive & (prof >= GREEN_THR), 1, 0)
        since += 1
        profit = bal - ACCT
        elig = alive & (tdays >= MIN_TDAYS) & (greens >= MIN_GREEN) & (since >= pay_cycle) & (WD_FRAC*profit >= WD_MIN)
        w = np.where(elig, np.minimum(WD_FRAC*profit, WD_CAP), 0.0)
        bal = bal - w; cum += w; npay += (w > 0); since = np.where(w > 0, 0, since)
    life = np.where(alive, cap, life)
    income = cum*SPLIT                       # trader keeps 90%
    return dict(income=income, cum=cum, npay=npay, life=life, blown=~alive)

def ftmo_funded_mc(days, risk_d, N=80000, cap=504, seed=3, block=5, pay_cycle=10):
    """FTMO 15k funded, SAME engine/strategy for apples-to-apples. Rules: $15k, STATIC
    floor $13,500 (=$1,500 below breakeven, does NOT trail), 3% ($450) daily intraday
    limit, 90/10. Withdraw ALL profit above breakeven every pay_cycle days (the $1,500
    structural cushion stays). Breach checked on intraday floating equity (day_min_R)."""
    acct, floor, daily, split = 15000.0, 13500.0, 450.0, 0.90
    rng = np.random.default_rng(seed)
    dR = np.asarray(days["day_R"], float); dmin = np.asarray(days["day_min_R"], float)
    nD = len(dR); nb = int(np.ceil(cap/block))
    idx = ((rng.integers(0,nD,size=(N,nb))[:,:,None]+np.arange(block)[None,None,:])%nD).reshape(N,-1)[:,:cap]
    Rd = dR[idx]; Rm = dmin[idx]
    bal = np.full(N, acct); alive = np.ones(N, bool); cum = np.zeros(N)
    npay = np.zeros(N, int); life = np.full(N, cap); since = np.zeros(N, int)
    for t in range(cap):
        rmin = Rm[:, t]*risk_d                                  # intraday floating $ vs day start
        dead = alive & ((rmin <= -daily) | (bal + rmin <= floor))   # 3% daily OR static floor
        life = np.where(dead, t, life); alive &= ~dead
        bal = np.where(alive, bal + Rd[:, t]*risk_d, bal)      # close the day
        since += 1
        w = np.where(alive & (since >= pay_cycle) & (bal > acct), bal - acct, 0.0)  # pull profit to BE
        bal = bal - w; cum += w; npay += (w > 0); since = np.where(w > 0, 0, since)
    life = np.where(alive, cap, life)
    return dict(income=cum*split, cum=cum, npay=npay, life=life, blown=~alive)

def golden():
    """Hand checks of the funded rules on crafted day sequences (scalar reference)."""
    def ref(seq, risk_d, cap=None, pay_cycle=5):
        bal=ACCT; peak=ACCT; cum=0.0; td=0; gr=0; since=10**6; alive=True; npay=0
        for prof_R in seq:
            prof=prof_R*risk_d; bal+=prof
            floor=min(peak-MAXDD, ACCT)
            if bal<=floor: return ("blow", round(cum,2), npay)
            peak=max(peak,bal); td+=1; gr+= (1 if prof>=GREEN_THR else 0); since+=1
            profit=bal-ACCT
            if td>=MIN_TDAYS and gr>=MIN_GREEN and since>=pay_cycle and WD_FRAC*profit>=WD_MIN:
                w=min(WD_FRAC*profit, WD_CAP); bal-=w; cum+=w; npay+=1; since=0
        return ("alive", round(cum,2), npay)
    # 5 green days of +$400 each (risk 1000, +0.4R) -> profit $2000 after day5; eligible;
    #   withdraw min(0.5*2000,1000)=1000 on day5. cum=1000.
    print("  golden A:", ref([0.4]*5, 1000))            # expect ('alive', 1000.0, 1)
    # trail-before-lock blow: +0.5 (bal25500,peak25500,floor24500) then -1.1 -> bal24400<=24500 blow
    print("  golden B:", ref([0.5,-1.1], 1000))         # expect ('blow', 0, 0)
    # lock then survive small dip: +1.0(bal26000,floor=min(25000,25000)=25000) then -0.9(bal25100>25000 ok)
    print("  golden C:", ref([1.0,-0.9,0.0,0.0,0.0], 1000))  # alive, no payout (only1 green day, profit<min)

def main():
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    # the verified eval winner (EU-open ORB); funded has no consistency/target, so re-optimise risk
    orders = S.orb(df, open_min=660, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
    days = lucid.build_days(engine.simulate(df, orders, cost_pts=COST), ad)

    print("="*88); print("LUCID 25K FUNDED — golden rule checks"); print("="*88)
    golden()

    print("\n"+"="*88)
    print("LUCID 25K FUNDED — lifetime income per account (trader's 90%), risk sweep")
    print("$25k, $1k DD locks at breakeven, no daily limit, 50%/cap$1k/min$500 payouts, 90/10")
    print("="*88)
    print("  (FEASIBLE sizes only: integer micros at the 60pt stop. 1 micro = $120 is the MIN for the")
    print("   validated 60pt edge — risking less needs a tighter stop, which DEGRADES the edge:")
    print("   25pt/1micro=$50 -> expR +0.09 & funded income ~$1,084 < the $120 row. So $120 is the floor.)")
    print(f"  {'risk$/trade':>11} {'micros':>7} | {'avg income$':>11} {'median$':>8} {'blow%':>6} "
          f"{'avg life(mo)':>12} {'avg #payouts':>12}")
    best=None
    for rd in [120, 240, 360, 480]:
        m = funded_mc(days, rd)
        inc = m["income"]; life_mo = m["life"]/lucid.MONTH
        row = (rd, inc.mean(), np.median(inc), m["blown"].mean(), life_mo.mean(), m["npay"].mean())
        if best is None or row[2] > best[2]: best = row
        print(f"  ${rd:<10.0f} {rd/(60*2):6.0f} | {inc.mean():10.0f} {np.median(inc):8.0f} "
              f"{m['blown'].mean()*100:5.0f}% {life_mo.mean():11.1f} {m['npay'].mean():11.1f}")

    luc_rd, luc_avg, luc_med, luc_blow, luc_life, luc_np = best
    print("-"*88)
    print(f"BEST Lucid: ${luc_rd:.0f}/trade -> avg income ${luc_avg:,.0f}/funded acct (median ${luc_med:,.0f})")

    # ---- FTMO 15k funded, SAME engine/strategy, risk sweep ----
    print("\n"+"="*88)
    print("FTMO 15K FUNDED (same engine/strategy) — lifetime income, risk sweep")
    print("$15k, STATIC $13,500 floor ($1,500 BELOW breakeven), 3% daily limit, 90/10, withdraw-all-to-BE")
    print("="*88)
    print(f"  {'risk$/trade':>11} | {'avg income$':>11} {'median$':>8} {'blow%':>6} {'avg life(mo)':>12} {'#payouts':>9}")
    fbest=None
    for rd in [40, 50, 60, 80, 100, 120, 160, 240]:
        m = ftmo_funded_mc(days, rd)
        inc = m["income"]; life_mo = m["life"]/lucid.MONTH
        row = (rd, inc.mean(), np.median(inc), m["blown"].mean(), life_mo.mean(), m["npay"].mean())
        if fbest is None or row[2] > fbest[2]: fbest = row
        print(f"  ${rd:<10.0f} | {inc.mean():10.0f} {np.median(inc):8.0f} {m['blown'].mean()*100:5.0f}% "
              f"{life_mo.mean():11.1f} {m['npay'].mean():8.1f}")
    ftmo_rd, ftmo_avg, ftmo_med, ftmo_blow, ftmo_life, ftmo_np = fbest
    print("-"*88)
    print(f"BEST FTMO: ${ftmo_rd:.0f}/trade -> avg income ${ftmo_avg:,.0f}/funded acct (median ${ftmo_med:,.0f})")

    # ---- efficiency head-to-head (USD), both modeled identically ----
    print("\n"+"="*88); print("EFFICIENCY: income per eval-dollar (both modeled on the SAME engine)"); print("="*88)
    luc_eval, luc_reset, luc_pass = 50.0, 60.0, 0.49     # Lucid EU 2-micro eventual pass
    ftmo_eval, ftmo_pass = 92.0, 0.47                    # $135 AUD ~ $92 USD, re-buy each fail
    luc_cost = luc_eval + (1/luc_pass - 1)*luc_reset
    ftmo_cost = ftmo_eval/ftmo_pass
    print(f"  {'':12}{'cost/funded':>12}{'avg income':>12}{'median income':>14}{'avg inc/$':>11}{'med inc/$':>11}")
    print(f"  {'Lucid 25k':12}${luc_cost:>10.0f}${luc_avg:>10,.0f}${luc_med:>12,.0f}{luc_avg/luc_cost:>10.1f}x{luc_med/luc_cost:>10.1f}x")
    print(f"  {'FTMO 15k':12}${ftmo_cost:>10.0f}${ftmo_avg:>10,.0f}${ftmo_med:>12,.0f}{ftmo_avg/ftmo_cost:>10.1f}x{ftmo_med/ftmo_cost:>10.1f}x")
    ratio = (luc_avg/luc_cost)/(ftmo_avg/ftmo_cost)
    print(f"\n  -> on AVG income per eval-dollar, Lucid is {ratio:.2f}x FTMO "
          f"({'Lucid' if ratio>1 else 'FTMO'} wins).")
    print("  Both right-skewed; compare medians too. Lucid: cheaper to fund but breakeven-locked")
    print("  floor blows it fast; FTMO: pricier but the $1,500-below-BE floor survives & extracts more.")

if __name__ == "__main__":
    main()
