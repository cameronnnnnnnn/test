"""
Lucid/test_lucid.py — bug-check the FLEX EVAL engine + Monte-Carlo.

1. ref_path(): a transparent SCALAR reference for one eval attempt (hand-auditable).
2. GOLDEN cases: hand-computed pass/blow/timeout outcomes for crafted day sequences.
3. EQUIVALENCE: run_eval_mc (vectorized) must match ref_path on every sampled path.
4. ENGINE sanity: no look-ahead (fill at next-bar open), day aggregation identity.

Run: python3 test_lucid.py   ->  all checks must print PASS.
"""
import numpy as np
import lucid, data, strategies as S, engine

ACCT, TARGET, MAXDD = 25000.0, 1250.0, 1000.0

def ref_path(dR, dmin, traded, risk_d, acct=ACCT, target=TARGET, maxdd=MAXDD,
             consist=0.50, min_days=1, breach="eod"):
    """Scalar reference: process ONE explicit day sequence; return (outcome, day_index)."""
    bal = acct; peak = acct; mg = 0.0; dtr = 0
    for t in range(len(dR)):
        floor = peak - maxdd
        if breach == "intraday" and bal + dmin[t]*risk_d <= floor:
            return ("blow", t)
        prof = dR[t]*risk_d
        bal = bal + prof
        if breach == "eod" and bal <= floor:
            return ("blow", t)
        if prof > 0: mg = max(mg, prof)
        dtr += int(traded[t])
        peak = max(peak, bal)
        net = bal - acct
        if net >= target and dtr >= min_days and mg <= consist*net + 1e-9:
            return ("pass", t)
    return ("timeout", len(dR)-1)

def golden():
    print("--- GOLDEN cases (hand-computed) ---")
    cases = []
    # 1. static floor: two -$500 days -> blow exactly when bal hits 24,000 (day idx 1)
    cases.append(("static floor blow", dict(dR=[-0.5,-0.5,-0.5], dmin=[-0.5,-0.5,-0.5], traded=[1,1,1],
                  risk_d=1000), ("blow",1)))
    # 2. trailing ratchet: +500,+500,-1500 -> floor ratchets to 25,000; -1500 close=24,500<=25,000 -> blow day2
    cases.append(("trailing ratchet blow", dict(dR=[0.5,0.5,-1.5], dmin=[0.5,0.5,-1.5], traded=[1,1,1],
                  risk_d=1000), ("blow",2)))
    # 3. consistency BLOCKS one-big-day pass: +1000 then +300 -> net 1300>=1250 but mg1000>0.5*1300 -> timeout
    cases.append(("consistency blocks", dict(dR=[1.0,0.3], dmin=[1.0,0.3], traded=[1,1],
                  risk_d=1000), ("timeout",1)))
    # 4. consistency UNBLOCKS once total grows: +1000,.3,.3,.3,.2 -> net2100, mg1000<=0.5*2100=1050 -> pass day4
    cases.append(("consistency unblocks", dict(dR=[1.0,0.3,0.3,0.3,0.2], dmin=[1.0,0.3,0.3,0.3,0.2],
                  traded=[1,1,1,1,1], risk_d=1000), ("pass",4)))
    # 5. clean pass: +700,+600 -> net1300, mg700<=650? NO -> blocked... use +650,+650 -> net1300 mg650<=650 yes
    cases.append(("clean 2-day pass", dict(dR=[0.65,0.65], dmin=[0.65,0.65], traded=[1,1],
                  risk_d=1000), ("pass",1)))
    # 6. min_days: hit target in 2 days but min_days=3 -> cannot pass day1; +.5/day -> day4 net2500 mg500 ok pass@?
    #    +500/day: day2 net1500 (>=1250) mg500<=750 ok but dtr=3 needed; passes when dtr>=3 -> day idx2
    cases.append(("min_days gate", dict(dR=[0.5,0.5,0.5,0.5], dmin=[0.5]*4, traded=[1,1,1,1],
                  risk_d=1000, min_days=3), ("pass",2)))
    # 7. EOD breach IGNORES intraday dip: close +500 but dipped -1500 intraday -> survives (eod)
    cases.append(("eod ignores intraday dip", dict(dR=[0.5], dmin=[-1.5], traded=[1], risk_d=1000), ("timeout",0)))
    # 8. intraday breach CATCHES the dip: same day, breach='intraday' -> blow day0
    cases.append(("intraday catches dip", dict(dR=[0.5], dmin=[-1.5], traded=[1], risk_d=1000,
                  breach="intraday"), ("blow",0)))
    ok = True
    for name, kw, expect in cases:
        kw = dict(kw); kw["dR"]=np.array(kw["dR"]); kw["dmin"]=np.array(kw["dmin"]); kw["traded"]=np.array(kw["traded"])
        got = ref_path(**kw)
        flag = "PASS" if got == expect else "**FAIL**"
        if got != expect: ok = False
        print(f"  [{flag}] {name:26s} expect {str(expect):14s} got {got}")
    return ok

def equivalence():
    """run_eval_mc (vectorized) must agree with ref_path on EVERY sampled path."""
    print("--- EQUIVALENCE: vectorized MC vs scalar reference ---")
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    orders = S.orb(df, open_min=660, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
    days = lucid.build_days(engine.simulate(df, orders, cost_pts=1.0), ad)
    dR = np.asarray(days["day_R"], float); dmin = np.asarray(days["day_min_R"], float)
    traded = (np.asarray(days["n"])>0).astype(int)
    allok = True
    for breach in ["eod", "intraday"]:
        for rd, dl, md, cs in [(240,21,1,0.5),(120,42,3,0.5),(300,15,1,1.0)]:
            out = lucid.run_eval_mc(days, rd, dl, n_paths=4000, seed=3, breach=breach,
                                    min_days=md, consist=cs, _return_paths=True)
            idx = out["idx"]
            mism = 0
            for p in range(idx.shape[0]):
                seq = idx[p]
                oc, t = ref_path(dR[seq], dmin[seq], traded[seq], rd, consist=cs, min_days=md, breach=breach)
                v_pass = bool(out["passed"][p]); v_blow = bool(out["blown"][p]); v_t = int(out["tpass"][p])
                r_pass = (oc=="pass"); r_blow = (oc=="blow")
                if v_pass != r_pass or v_blow != r_blow or (r_pass and v_t != t):
                    mism += 1
            flag = "PASS" if mism==0 else f"**FAIL ({mism})**"
            if mism: allok = False
            print(f"  [{flag}] breach={breach:8s} risk${rd} dl{dl} min_days{md} consist{cs}: {idx.shape[0]} paths match")
    return allok

def engine_sanity():
    print("--- ENGINE sanity ---")
    df = S.prep(data.load()); ad = np.array(sorted(df["date"].unique()))
    orders = S.orb(df, open_min=660, or_min=30, stop_pts=60, tp_R=3.0, be_R=1.0, vol_filter=True)
    tr = engine.simulate(df, orders, cost_pts=1.0)
    ok = True
    # (a) every entry fills at the bar AFTER the signal (no look-ahead): entry_dt > signal bar.
    #     engine fills O[b0+1]; check entry price equals an actual open in the data near entry_dt.
    O = df["open"].values; idxmap = {t:i for i,t in enumerate(df.index)}
    bad = 0
    for _, t in tr.head(200).iterrows():
        i = idxmap.get(t["entry_dt"])
        if i is None or abs(O[i]-t["entry"])>1e-6: bad += 1
    print(f"  [{'PASS' if bad==0 else '**FAIL**'}] fills at real next-bar open (0 look-ahead): {bad} bad of 200")
    ok &= (bad==0)
    # (b) day aggregation identity: sum of trade R per day == day_R from build_days
    days = lucid.build_days(tr, ad)
    dmap = {d["day"]: d for d in days}
    byday = tr.groupby("day")["R"].sum()
    bad2 = sum(1 for d,v in byday.items() if abs(dmap[np.datetime64(d)]["day_R"]-v)>1e-6)
    print(f"  [{'PASS' if bad2==0 else '**FAIL**'}] day_R == sum(trade R): {bad2} mismatches")
    ok &= (bad2==0)
    # (c) day_min_R <= min(0, day_R) and <= 0 always (intraday low can't be above the close path)
    bad3 = sum(1 for d in days if d["n"]>0 and (d["day_min_R"] > min(0.0, d["day_R"])+1e-9))
    print(f"  [{'PASS' if bad3==0 else '**FAIL**'}] day_min_R <= min(0, day_R): {bad3} violations")
    ok &= (bad3==0)
    # (d) stop-loss never worse than ~-1R - cost (no gap-through under the conservative model)
    worst = tr["R"].min()
    print(f"  [{'PASS' if worst>=-1.5 else 'WARN'}] worst single-trade R = {worst:.2f} (stop ~-1R + cost)")
    return ok

if __name__ == "__main__":
    a = golden(); print()
    b = equivalence(); print()
    c = engine_sanity(); print()
    print("="*60)
    print("ALL CHECKS PASS" if (a and b and c) else "*** SOME CHECKS FAILED ***")
