"""
FairPriceStrategy/fairprice.py — faithful implementation of the "fair pricing theory" strategy
(from the video transcription; see README). Core ideas:

  * The candle immediately BEFORE a session open is the session's FAIR PRICE anchor. Moves away
    from it right after the open are "unfair" (opening flow / new participants), so:
      PHASE 1 (0-10 min):  trade CONTINUATION of the opening candle's direction (the unfair move).
      PHASE 2 (10-90 min): trade REVERSION back toward the fair price, only with room in favor.
  * Entries: DISPLACEMENT candle (body > prior body x mult, tiny wicks) or BREAK OF STRUCTURE
    with a close beyond a fractal swing — in the phase's direction. A+ = both triggers, A = one.
  * Sessions (EST->server EET = +7h): 18:00 reopen->01:00, 20:00 Asia->03:00, 03:00 London->10:00,
    08:30 news->15:30, 09:30 NY->16:30 (primary), 14:00 NY PM->21:00.
  * Fixed 25pt stop / 38pt target (1:1.5) as specified — configurable, no magic numbers.
  * Session discipline: first qualifying setup only in phase 1; max N (4) accepted trades per
    session; phase 2 stops after its first loss (bias broken). Sequential: a new trade can only
    be accepted after the prior one has exited.

Honesty: 70/30 train/test, per-session edge, grading breakdown, then the thing the video itself
says is the only metric that matters — the FTMO pass rate (MC under full rules).
Run: python3 fairprice.py
"""
import os, sys
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
for rel in (("..", "ftmo", "v4"), ("..", "challengephasev3")):
    p = os.path.normpath(os.path.join(HERE, *rel))
    if p not in sys.path: sys.path.insert(0, p)
import data, strategies as S, engine, ftmo             # noqa: E402
from engine import ExitSpec                              # noqa: E402
from search import build_days                            # noqa: E402

# ---------------- configuration (all tunable, defaults per the video) ----------------
CFG = dict(
    stop_pts=25.0, tp_pts=38.0,        # 1 : 1.52 fixed R:R
    disp_mult=1.0,                     # displacement body > this x prior body
    wick_max=0.35,                     # max (range-body)/range for a displacement candle
    swing_k=2,                         # fractal width for structure
    bos_lookback=45,                   # bars back a swing stays relevant
    cont_win=10,                       # phase-1 window (minutes after open)
    rev_win=90,                        # phase-2 ends this many minutes after open
    min_room=30.0,                     # phase-2 needs at least this many pts back to fair
    max_per_session=4,                 # accepted trades per session cap
    stop_after_rev_loss=True,          # phase 2 halts after its first loss
    cost_pts=2.0,
)
SESS = {"reopen": 1*60, "asia": 3*60, "london": 10*60, "news": 15*60+30,
        "nyam": 16*60+30, "nypm": 21*60}


def fractal_swings(h, l, k):
    n = len(h)
    swH = np.zeros(n, bool); swL = np.zeros(n, bool)
    for i in range(k, n-k):
        if h[i] == max(h[i-k:i+k+1]) and h[i] > h[i-1] and h[i] > h[i+1]: swH[i] = True
        if l[i] == min(l[i-k:i+k+1]) and l[i] < l[i-1] and l[i] < l[i+1]: swL[i] = True
    return swH, swL


def session_orders(df, cfg=CFG):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    tod = df["tod"].values
    body = np.abs(c - o); rng = np.maximum(h - l, 1e-9)
    wickr = (rng - body) / rng
    cand_dir = np.sign(c - o)
    orders = []
    for day, gi in df.groupby("date").indices.items():
        t = tod[gi]
        for sname, om in SESS.items():
            sess = gi[(t >= om) & (t < om + cfg["rev_win"])]
            pre = gi[t < om]
            if len(sess) < 20 or len(pre) < 3:
                continue
            fair = c[pre[-1]]                                   # fair price = pre-open candle close
            ob = sess[0]                                        # opening candle
            cdir = cand_dir[ob]
            if cdir == 0:
                continue
            # fractal swings over pre-open tail + session (local index space)
            win = np.concatenate([pre[-cfg["bos_lookback"]:], sess])
            swH, swL = fractal_swings(h[win], l[win], cfg["swing_k"])
            base = len(win) - len(sess)                          # first session bar in local idx
            spec = ExitSpec(tp_R=cfg["tp_pts"]/cfg["stop_pts"], be_R=0.0, trail_R=0.0,
                            max_bars=cfg["rev_win"])
            got_p1 = False
            for j in range(1, len(sess) - 1):
                b = sess[j]; lm = base + j
                mins = tod[b] - om
                phase = 1 if mins <= cfg["cont_win"] else 2
                if phase == 1 and got_p1:
                    continue
                if phase == 1:
                    d = int(cdir)
                else:
                    d = int(np.sign(fair - c[b]))
                    if d == 0 or abs(fair - c[b]) < cfg["min_room"]:
                        continue
                # trigger 1: displacement in direction d
                disp = (cand_dir[b] == d and body[b] > cfg["disp_mult"]*body[b-1]
                        and wickr[b] <= cfg["wick_max"])
                # trigger 2: break of structure + close beyond, in direction d
                bos = False
                if d > 0:
                    # unbroken swing highs: no close between the swing and now above the level
                    lvls = [h[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                            if swH[i2] and (c[win[i2+1:lm]] <= h[win[i2]]).all()]
                    if lvls and c[b] > min(lvls):
                        bos = True
                else:
                    lvls = [l[win[i2]] for i2 in range(max(0, lm-cfg["bos_lookback"]), lm-1)
                            if swL[i2] and (c[win[i2+1:lm]] >= l[win[i2]]).all()]
                    if lvls and c[b] < max(lvls):
                        bos = True
                if not (disp or bos):
                    continue
                grade = "A+" if (disp and bos) else "A"
                orders.append(dict(entry_bar=b, dir=d, stop_pts=cfg["stop_pts"], spec=spec,
                                   eod_bar=sess[-1], day=day,
                                   tag=f"{sname}|P{phase}|{grade}"))
                if phase == 1:
                    got_p1 = True
    return orders


def sequential_filter(tr, cfg=CFG):
    """Session discipline: trades in time order; next only after prior exit; cap per session;
    phase 2 stops after its first loss."""
    tr = tr.copy()
    tr["sess"] = tr["tag"].str.split("|").str[0]
    tr["phase"] = tr["tag"].str.split("|").str[1]
    keep = []
    for (day, sess), g in tr.groupby(["day", "sess"]):
        g = g.sort_values("entry_dt")
        last_exit = None; n_acc = 0; rev_dead = False
        for i, r in g.iterrows():
            if n_acc >= cfg["max_per_session"]: break
            if last_exit is not None and r["entry_dt"] <= last_exit: continue
            if r["phase"] == "P2" and rev_dead: continue
            keep.append(i); n_acc += 1; last_exit = r["exit_dt"]
            if cfg["stop_after_rev_loss"] and r["phase"] == "P2" and r["R"] < 0:
                rev_dead = True
    return tr.loc[keep]


def main():
    df = S.prep(data.load())
    ad = np.array(sorted(df["date"].unique())); cut = ad[int(len(ad)*0.7)]
    print("Simulating fair-price strategy (all sessions, all candidates) ...")
    raw = engine.simulate(df, session_orders(df), cost_pts=CFG["cost_pts"])
    tr = sequential_filter(raw)
    tr["sess"] = tr["tag"].str.split("|").str[0]
    tr["phase"] = tr["tag"].str.split("|").str[1]
    tr["grade"] = tr["tag"].str.split("|").str[2]
    print(f"candidates {len(raw)} -> accepted after session discipline {len(tr)} "
          f"({len(tr)/len(ad):.1f}/day)\n")

    def es(g):
        if not len(g): return "     -"
        e = engine.edge_stats(g)
        return f"n={e['n']:5d} WR {e['wr']*100:4.1f}% expR {e['expR']:+.3f}"
    print(f"{'':14}{'TRAIN':>36}{'TEST':>36}")
    for key, vals in [("sess", list(SESS)), ("phase", ["P1", "P2"]), ("grade", ["A+", "A"])]:
        for v in vals:
            g = tr[tr[key] == v]
            print(f"  {key}={v:8} {es(g[g['day']<=cut]):>36} {es(g[g['day']>cut]):>36}")
        print()
    print(f"  {'ALL':10} {es(tr[tr['day']<=cut]):>36} {es(tr[tr['day']>cut]):>36}")

    # ---- FTMO MC: the only metric that matters (per the video, correctly) ----
    print("\nFTMO 15k 1-Step MC (block bootstrap, -2R daily breaker):")
    days_all = build_days(tr, ad, 2.0)
    dte = ad[ad > cut]
    days_te = build_days(tr[tr["day"].isin(set(dte))], dte, 2.0)
    for lbl, dd in [("ALL ", days_all), ("OOS ", days_te)]:
        best = (-1, None, None)
        for r in (0.0035, 0.005, 0.0075, 0.01, 0.0125):
            m = ftmo.run_mc(dd, r, 20, n_paths=40000, seed=11, block=5)
            if m["pass_rate"] > best[0]: best = (m["pass_rate"], r, m)
        p, r, m = best
        m40 = ftmo.run_mc(dd, r, 40, n_paths=40000, seed=11, block=5)
        print(f"  [{lbl}] 20d pass {p*100:4.1f}% blow {m['blow_rate']*100:4.1f}% (risk {r*100:.2f}%)"
              f"   40d pass {m40['pass_rate']*100:4.1f}%")
    print("\nReference: 52p ~55%/72% (20d/40d), 52pPlus ~58%/75%.")


if __name__ == "__main__":
    main()
