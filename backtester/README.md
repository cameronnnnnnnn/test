# NAS100 prop-firm manual backtester

Single self-contained `index.html`. Open it in Chrome — no server, no build, no external requests.

## Getting started
1. Open `backtester/index.html` in Chrome.
2. Drag your MT5 **NAS100 M1 CSV** onto the window (or use the file picker). ~63MB / 1.04M bars
   parses in a Web Worker and is cached in IndexedDB, so every later open is instant.
   (`Load synthetic demo data` gives you fake bars to try the UI — clearly not real prices.)
3. Set a date with the datetime box → **Go**, then step with `→` / play with `Space`.

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
dropdown or keys `1`–`9`. **Mirror mode** fires one order into every mirror-enabled account, each
sized by its own risk setting and contract cap.

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

## Verification
Tested in Chromium against the real NAS100 export (49,619-bar slice): data load and sort, exact
NY session mapping, no-look-ahead, session jump, fills/commission/R, all three drawdown floors
(incl. TopStep lock), breach detection, multi-account independence with mirror, stats, CSV,
session round-trip, drawing tools, journal determinism, auto-flat, and ambiguous-bar policy.
One real bug was caught this way: the sample contains 37 session closes but only 36 exact 16:59
bars, so auto-flat now uses a crossing test instead of an exact-minute match.
