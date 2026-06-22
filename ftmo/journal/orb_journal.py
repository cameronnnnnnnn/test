#!/usr/bin/env python3
"""
ORB trade journal — SQLite-backed trade tracking + FTMO debriefs.

Why SQLite + a CSV bridge (not the MetaTrader5 python package):
  Your MT5 runs on Linux under Wine, where the official MetaTrader5 python package
  doesn't run cleanly. The bulletproof, OS-independent path is: the EA appends every
  closed trade to a CSV file; this tool ingests that CSV into a single-file SQLite DB
  and generates debriefs. SQLite = zero-config, one file, full SQL, perfect at this
  scale, and trivially synced into the repo so your history compounds over time.

Trade R-multiples are computed the SAME way as the backtest (price move / stop distance),
so live debriefs are directly comparable to the Monte-Carlo edge stats.

Usage:
  python3 orb_journal.py init
  python3 orb_journal.py ingest <history.csv> [--stop 80] [--start 15000]
  python3 orb_journal.py snapshot --balance 15123 --equity 15098
  python3 orb_journal.py debrief [--start 15000] [--stop 80] [--out debrief.md]

Accepts two CSV shapes (auto-detected):
  (A) EA journal  : ticket,symbol,type,volume,open_time,open_price,close_time,close_price,sl,profit,commission,swap,comment
  (B) MT5 export  : the "History" tab exported to CSV (column names auto-mapped).
"""
import sqlite3, csv, sys, os, argparse, datetime as dt

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orb_journal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades(
  ticket      INTEGER PRIMARY KEY,
  symbol      TEXT,
  direction   TEXT,           -- buy / sell
  volume      REAL,
  open_time   TEXT,
  open_price  REAL,
  close_time  TEXT,
  close_price REAL,
  sl          REAL,
  profit      REAL,           -- net account currency (incl comm+swap if provided)
  commission  REAL,
  swap        REAL,
  session     TEXT,           -- 15 / 16 (from comment or open hour)
  r_multiple  REAL,           -- direction*(close-open)/stop
  comment     TEXT
);
CREATE TABLE IF NOT EXISTS snapshots(
  ts      TEXT PRIMARY KEY,
  balance REAL,
  equity  REAL,
  note    TEXT
);
"""

def conn(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    with conn() as c: c.executescript(SCHEMA)
    print(f"initialized {DB}")

def _f(x):
    try: return float(str(x).replace(" ","").replace(",",""))
    except: return None
def _parse_time(s):
    s=str(s).strip()
    for fmt in ("%Y.%m.%d %H:%M:%S","%Y.%m.%d %H:%M","%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M","%Y/%m/%d %H:%M:%S"):
        try: return dt.datetime.strptime(s,fmt).isoformat()
        except: pass
    return s or None

def _norm(row, keys):
    # case/space-insensitive column lookup
    low={k.lower().strip():v for k,v in row.items() if k}
    for want in keys:
        if want in low and str(low[want]).strip()!="": return low[want]
    return None

def ingest(path, stop=80.0, start=15000.0):
    init()
    n=0; ins=0
    with conn() as c, open(path,newline="",encoding="utf-8-sig") as f:
        rd=csv.DictReader(f)
        for row in rd:
            n+=1
            ticket=_norm(row,["ticket","position","order","deal","#"])
            otime=_parse_time(_norm(row,["open_time","time","open time","opened"]) or "")
            ctime=_parse_time(_norm(row,["close_time","close time","closed"]) or otime or "")
            op=_f(_norm(row,["open_price","price_open","open price","price"]))
            cp=_f(_norm(row,["close_price","price_close","close price"]))
            typ=(_norm(row,["type","direction","side"]) or "").lower()
            direction="buy" if "buy" in typ or typ in("0","long") else ("sell" if ("sell" in typ or typ in("1","short")) else typ)
            profit=_f(_norm(row,["profit","pnl","net profit","p/l"])) or 0.0
            comm=_f(_norm(row,["commission","comm"])) or 0.0
            swap=_f(_norm(row,["swap"])) or 0.0
            comment=_norm(row,["comment","comments"]) or ""
            sl=_f(_norm(row,["sl","s/l","stop"]))
            vol=_f(_norm(row,["volume","lots","size"]))
            if ticket is None or op is None or cp is None:  # skip non-trade / balance rows
                continue
            # session from comment (ORB15/ORB16) or open hour
            session=""
            for tag in ("15","16","14","17"):
                if tag in (comment or ""): session=tag; break
            if not session and otime:
                try: session=str(dt.datetime.fromisoformat(otime).hour)
                except: pass
            sign=1 if direction=="buy" else -1
            r=round(sign*(cp-op)/stop,3) if stop else None
            try:
                c.execute("""INSERT OR REPLACE INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (int(float(ticket)),_norm(row,["symbol","instrument"]) or "",direction,vol,
                     otime,op,ctime,cp,sl,profit+comm+swap,comm,swap,session,r,comment))
                ins+=1
            except Exception as e:
                print(f"  row {n}: skipped ({e})")
    print(f"ingested {ins} trades from {path} ({n} rows scanned). stop={stop} for R-multiples.")

def snapshot(balance,equity,note=""):
    init()
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)",
                  (dt.datetime.now().isoformat(timespec="seconds"),balance,equity,note))
    print(f"snapshot saved: balance={balance} equity={equity}")

def debrief(start=15000.0, stop=80.0, out=None):
    with conn() as c:
        tr=[dict(r) for r in c.execute("SELECT * FROM trades ORDER BY close_time")]
        snaps=[dict(r) for r in c.execute("SELECT * FROM snapshots ORDER BY ts")]
    L=[]; p=L.append
    if not tr:
        print("no trades in journal yet. ingest a CSV first."); return
    Rs=[t["r_multiple"] for t in tr if t["r_multiple"] is not None]
    profits=[t["profit"] for t in tr]
    wins=[r for r in Rs if r>0]; losses=[r for r in Rs if r<=0]
    # running balance from start + cumulative profit
    bal=start; curve=[start]
    for t in tr: bal+=t["profit"]; curve.append(bal)
    peak=max(curve); cur=curve[-1]
    floor=peak*0.90                       # 10% trailing DD (simplified)
    target=start*1.10
    # today's P&L vs 3% daily
    today=dt.date.today().isoformat()
    today_pl=sum(t["profit"] for t in tr if (t["close_time"] or "")[:10]==today)
    daily_limit=-0.03*(cur-today_pl if cur-today_pl>0 else start)

    p("# ORB account debrief")
    p(f"_generated {dt.datetime.now().isoformat(timespec='minutes')}_\n")
    p("## FTMO status")
    p(f"- Balance: **${cur:,.2f}**  (start ${start:,.0f}, peak ${peak:,.2f})")
    p(f"- P&L: **{(cur/start-1)*100:+.2f}%**  →  target +10% = ${target:,.0f} "
      f"({'**REACHED**' if cur>=target else f'${target-cur:,.0f} to go'})")
    p(f"- Trailing 10% DD floor: ${floor:,.2f}  (cushion: **${cur-floor:,.2f}** = {(cur-floor)/cur*100:.1f}%)")
    p(f"- Today P&L: ${today_pl:+,.2f}  (3% daily stop ≈ ${daily_limit:,.2f})"
      + ("  ⚠️ **near daily limit**" if today_pl<0.6*daily_limit else ""))
    p("")
    p("## Edge (live, vs backtest expR≈+0.125, WR≈31%)")
    n=len(Rs)
    wr=100*len(wins)/n if n else 0
    expR=sum(Rs)/n if n else 0
    pf=(sum(wins)/-sum(losses)) if losses and sum(losses)<0 else float("inf")
    p(f"- Trades: **{n}**  |  Win rate: **{wr:.1f}%**  |  Expectancy: **{expR:+.3f} R/trade**")
    p(f"- Profit factor: **{pf:.2f}**  |  Best: {max(Rs):+.1f}R  Worst: {min(Rs):+.1f}R  |  Net: ${sum(profits):+,.2f}")
    if n>=10 and (wr<22 or expR<0):
        p(f"- ⚠️ live edge running below backtest — small sample, but watch it.")
    p("")
    # by session and direction
    def grp(key):
        g={}
        for t in tr:
            k=t[key] or "?"; g.setdefault(k,[]).append(t["r_multiple"])
        return g
    p("## By session")
    for k,v in sorted(grp("session").items()):
        vv=[x for x in v if x is not None]
        if vv: p(f"- session {k}: {len(vv)} trades, WR {100*sum(x>0 for x in vv)/len(vv):.0f}%, expR {sum(vv)/len(vv):+.3f}")
    p("\n## By direction")
    for k,v in sorted(grp("direction").items()):
        vv=[x for x in v if x is not None]
        if vv: p(f"- {k}: {len(vv)} trades, WR {100*sum(x>0 for x in vv)/len(vv):.0f}%, expR {sum(vv)/len(vv):+.3f}")
    p("\n## Last 10 trades")
    p("| close | sym | dir | R | profit |")
    p("|---|---|---|---|---|")
    for t in tr[-10:]:
        p(f"| {(t['close_time'] or '')[:16]} | {t['symbol']} | {t['direction']} | "
          f"{(t['r_multiple'] if t['r_multiple'] is not None else 0):+.2f} | ${t['profit']:+,.2f} |")
    report="\n".join(L)
    print(report)
    if out:
        with open(out,"w") as f: f.write(report+"\n")
        print(f"\n[written to {out}]")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd")
    sub.add_parser("init")
    pi=sub.add_parser("ingest"); pi.add_argument("csv"); pi.add_argument("--stop",type=float,default=80.0); pi.add_argument("--start",type=float,default=15000.0)
    ps=sub.add_parser("snapshot"); ps.add_argument("--balance",type=float,required=True); ps.add_argument("--equity",type=float,required=True); ps.add_argument("--note",default="")
    pd_=sub.add_parser("debrief"); pd_.add_argument("--start",type=float,default=15000.0); pd_.add_argument("--stop",type=float,default=80.0); pd_.add_argument("--out",default=None)
    a=ap.parse_args()
    if a.cmd=="init": init()
    elif a.cmd=="ingest": ingest(a.csv,a.stop,a.start)
    elif a.cmd=="snapshot": snapshot(a.balance,a.equity,a.note)
    elif a.cmd=="debrief": debrief(a.start,a.stop,a.out)
    else: ap.print_help()
