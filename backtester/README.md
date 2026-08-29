# NAS100 prop-firm manual backtester

Single self-contained `index.html`. Open it in Chrome — no server, no build, no external requests.

## Getting started
1. Open `backtester/index.html` in Chrome.
2. Drag your MT5 **NAS100 M1 CSV** onto the window (or use the file picker). ~63MB / 1.04M bars
   parses in a Web Worker and is cached in IndexedDB, so every later open is instant.
   (`Load synthetic demo data` gives you fake bars to try the UI — clearly not real prices.)
3. Set a date with the datetime box → **Go**, then step with `→` / play with `Space`.

## Order ticket, stops and breakeven
* The top bar holds a live **order ticket**: `SL` in points and `TP` in either points or **R**
  (click the `pts` / `R` toggle). It shows the resulting RR and the position size your active
  account would take. `Buy` / `Sell` (or `B` / `S`) fire at those distances.
* **SL and TP are measured from the actual fill**, not the signal price, so "SL 25" is exactly
  25 points of risk and a stop-out is exactly −1.00R.
* **Breakeven**: `B/E` button or `E` moves the stop of every open position to the entry (plus an
  optional offset in Execution settings, e.g. to cover commission). Stops moved to BE turn amber
  on the chart and exit with reason `BE`.
* **Auto-breakeven**: set *Auto B/E at R* in the Rules tab (0 = off). It arms at the **end** of the
  bar that reaches the trigger, so it can never rescue a trade inside the same bar.
* **Close half** (`½` or `X`), close a single position, or drag a live **stop / target line
  directly on the chart**. Right-click any open position for the same menu.

## The rules that keep results honest
* **No look-ahead.** Bars after the replay cursor are never rendered and never reachable. The
  `🔓 Free browse` button reveals the future for chart study only — it is OFF by default and shows
  a permanent warning while on.
* **Entries fill at the NEXT bar's open**, plus half the spread and your slippage setting.
* **Ambiguous bars resolve as a stop.** When a single 1m bar contains both your stop and your
  target, the trade is closed at the stop and flagged `!` in the trade log — 1m data can't tell
  which came first, and resolving it in your favour is exactly how manual backtests flatter
  themselves.
* Commission is charged per contract per side.

## Prop rule engine
Per account: start balance, profit target, max loss, **drawdown mode**
(`static` / `eod_trailing` / `intraday_trailing`), optional lock-at-start-balance (TopStep style),
daily loss limit (equity or balance), consistency %, min trading days, contract cap, mini/micro,
commission. The HUD shows live balance, the current floor, room to floor, distance to target,
days traded and consistency status, and flips to `FAILED` / `PASSED` the moment a rule triggers,
logging the exact reason and timestamp.

Notes on semantics:
* `intraday_trailing` ratchets the floor on **unrealized** highs (open-trade MFE), which is the
  harsh version Apex uses. `eod_trailing` only ratchets on end-of-day balance.
* A breach is evaluated against the bar's **worst** equity (open trades marked at the bar extreme).
* Passing is checked on **realized balance with no open positions**, plus min-days and (optionally)
  consistency. Consistency can either *block* the pass or merely *delay* it — your choice per firm.
* The trading day follows CME convention: the session that starts at 18:00 ET belongs to the **next**
  trade date. Daily limits and days-traded use that boundary.
* Positions auto-flatten at 16:59 ET by default (toggleable).

## Multi-account
Create any number of accounts with different rules. Every account is simulated on **every bar**,
independently — switching the active account never pauses or resets the others. Switch with the
dropdown or keys `1`–`9`.

* **Bulk create**: pick a preset, set a count, hit `+ Add` to spin up 10+ accounts at once.
  `⧉` clones the active account (rules, risk and sizing).
* **Mirror** (`M`) fires each order into every *enabled, still-active* account, sized by that
  account's own risk setting, contract cap and tick value. Toggle an account's `on` checkbox to
  include or exclude it — that is also how you stagger starts.
* Per-account sizing: **risk $** (contracts derived from the stop distance) or **fixed** contracts.
* Each card shows live balance, room to floor, distance to target, a progress bar, an **equity
  sparkline drawn between the floor and the target lines**, and trade/day/consistency counters.
  `◐` hides accounts that have already passed or failed.
* A portfolio summary tops the panel: active / passed / failed counts, total equity, combined P/L
  and aggregate win rate.

Performance: orders are indexed by bar, so stepping is O(1) per account per bar. Measured
**~700,000 bar-steps per second with 12 accounts live** in Chromium, and the account panel is
patched node-by-node during playback rather than re-rendered.

## Determinism (why your session survives)
Orders are stored in a per-account **journal** keyed to the bar you placed them on; all account
state is *derived* by replaying that journal. So changing a rule mid-session, dragging the
scrubber, or reloading a saved session re-simulates rather than losing trades. Stepping back
(`←`) deliberately discards orders placed at or after that bar — that is the undo.

## Files in / out
* Rule preset → `.json` (download, and drag-drop back on).
* Whole session (accounts + journal + drawings + cursor) → `.json`.
* Trades → CSV.

## Built-in presets
Apex 50K, Apex 100K, TopStep 50K, FTMO 15K 1-step, Goat Blitz 10K. **These are defaults from
public rule sheets, not gospel — check them against your firm's current terms before trusting a
result.** Every field is editable.

## Known approximations (stated, not hidden)
* If the browser refuses to start the Web Worker (some `file://` configurations), parsing falls
  back to the main thread and the tab will pause for a few seconds. Everything else is identical.
* Fills use bar OHLC, not tick data: intrabar sequence is unknowable, hence the conservative
  stop-first rule. Slippage is a flat user setting, not modelled per-event.
* Partial closes are supported by closing a position from the trade log; scaling out in fractions
  of a contract is not modelled.
* NY display times are computed exactly (per-hour DST resolution), so the 8:30 / 9:30 / 18:00
  session lines stay correct across DST changes in both zones.

## Feel / rendering
Everything runs off a single `requestAnimationFrame` loop with dirty flags — interactions set a
flag rather than forcing a synchronous redraw. Zoom is **anchored to the bar under the cursor**,
the price axis and time axis each drag to scale, and double-click resets. Only visible candles are
drawn.

## Verification
Tested in Chromium against the real NAS100 export (49,619-bar slice): data load and sort, exact
NY session mapping, no-look-ahead, session jump, fills/commission/R, all three drawdown floors
(incl. TopStep lock), breach detection, multi-account independence with mirror, stats, CSV,
session round-trip, drawing tools, journal determinism, auto-flat, and ambiguous-bar policy.
Two real bugs were caught this way:
1. The sample contains 37 session closes but only 36 exact 16:59 bars, so auto-flat now uses a
   crossing test instead of an exact-minute match (otherwise a position leaked overnight).
2. When SL/TP became fill-relative, the journal replay was still rebuilding orders from absolute
   prices only — reloading a session silently dropped the stops. Caught by the round-trip check
   (8 trades became 5); the journal now carries every order field.

v2 re-verified: ticket SL 25 / TP 50 produces exactly 25.0 and 50.0 points and a −1.00R stop-out;
breakeven moves the stop to the fill and survives replay, exiting as `BE`; auto-B/E arms at
mfe 30.2 vs 30.0 risk (1R); close-half splits 4 → 2 with a `partial` record; 12 accounts across
5 firms step at ~700k bars/sec; session round-trip reproduces balance and trade count exactly.
