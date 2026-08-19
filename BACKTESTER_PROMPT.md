# Paste-ready prompt: build the prop-firm manual backtester

Copy everything inside the fence and send it as a new message.

---

```
Build me a manual (discretionary) backtesting app that looks and feels like TradingView, purpose-built
for prop-firm challenge practice. Deliver it as ONE self-contained .html file I open locally in Chrome —
no server, no build step, no CDN/external requests, everything inline. Write it into a new folder
`backtester/` in the repo and commit it.

## DATA
- 1-minute bars only. I drag-and-drop my MT5 CSV exports onto the app; it parses and caches to IndexedDB
  so reopening is instant. Show a parse progress bar; use a Web Worker so the UI never freezes.
- Support BOTH export formats I have (auto-detect):
  (a) NAS100: tab-separated, header `"DateTime  Open  High  Low  Close  Volume  TickVolume"`, first and
      last fields wrapped in double-quotes, datetime `2025.10.01 07:12:00`, rows REVERSE-chronological.
  (b) FX/GER40: tab-separated, header `DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD`,
      date `2021.01.04`, time `00:04:00`, ascending. The SPREAD column is in points — use it for
      realistic per-bar spread when present.
- Store as typed arrays (Float32/Int32), not objects. Must handle 2M+ bars smoothly.
- Timestamps in the files are broker server time (EET/EEST). Add a timezone selector (Server / New York /
  London / Sydney) that only changes DISPLAY — never the underlying data. Default view New York, because
  I think in ET session times.

## CHART (canvas, not DOM)
- Candlesticks with wicks, TradingView-style dark theme; blue/green up, black/red down (configurable).
- Smooth pan (drag), zoom (scroll), price-axis drag to scale, time-axis drag to compress, double-click to
  reset. 60fps at 1M+ bars via viewport slicing — only render visible candles.
- Crosshair with price/time labels on both axes, OHLC + change readout in a top-left legend.
- Session shading and vertical session lines I can toggle: 6:00pm ET reopen, 9:30am ET open, 8:30am ET,
  4:59pm ET close, plus the 5-6pm ET halt gap drawn as a visible break.
- Horizontal grid, last-price line, and a "today's high/low" and "prior day close" auto-line toggle.

## REPLAY (the core of manual backtesting) — NO LOOK-AHEAD, EVER
- Jump to any date/time, then step the chart forward bar-by-bar. Future bars must be completely hidden and
  unreachable (don't render them, don't let zoom-out reveal them).
- Controls: step 1 bar (right arrow), step back (left arrow, undoes state), play/pause (space), speed
  selector (1x/5x/20x/max), jump forward N minutes, and "jump to next session open".
- A visible "replay cursor" marker and a date/time display of the current replay bar.

## DRAWING TOOLS (must be draggable/editable after placement, persisted per instrument)
- Long Position and Short Position tools EXACTLY like TradingView: drag to set entry, stop, target; shows
  RR ratio, points risked/gained, $ risk and $ P/L based on the ACTIVE account's contract size; drag any
  of the three handles to adjust; snap-to-price option.
- Horizontal line, horizontal RAY, trendline, vertical line, rectangle, measure tool.
- Right-click any drawing to edit color/thickness/delete. Undo/redo (Ctrl+Z / Ctrl+Shift+Z).
- Drawings persist across replay stepping and reload (IndexedDB).

## TRADING
- Place trades at the replay cursor: market buy/sell, or convert a position tool directly into a live trade
  ("Execute" button on the position tool).
- Each trade has entry, stop, target, size (contracts). Support partial closes and moving stop/target
  mid-trade (drag on chart while replay is paused).
- FILL REALISM (important — do not make this optimistic):
  * Entries fill at the NEXT bar's open, plus spread and configurable slippage.
  * If a bar's range contains BOTH stop and target, resolve as STOP HIT (conservative). Show a warning
    badge on that trade so I know it was ambiguous.
  * Apply commission per contract per side, and spread from the data's spread column if available,
    otherwise a fixed points value I set.
- Trade log panel: entry/exit time, direction, size, points, R multiple, $, MAE/MFE, exit reason
  (TP/SL/manual/EOD/ambiguous).

## PROP FIRM ENGINE (the whole point)
Configurable rule set per account:
- starting balance, profit target ($ or %)
- max loss amount, and DRAWDOWN MODE: `static` (fixed floor from start), `eod_trailing` (trails end-of-day
  equity peak), `intraday_trailing` (trails the intraday/open-trade peak — must ratchet on unrealized MFE)
- optional drawdown lock (trailing floor stops rising once it reaches start balance, TopStep-style)
- daily loss limit (optional, off for firms without one) and whether it's measured on equity or balance
- consistency rule % (best day must be <= X% of total profit) — show live status, and whether violating it
  BLOCKS the pass or just delays it
- minimum trading days, maximum days (optional)
- contract cap (e.g. 6 minis / 60 micros), tick value, tick size, commission, per-instrument point value
- Live HUD showing: current balance, current floor/threshold price, distance to floor, distance to target,
  days traded, consistency status, and a big PASS / FAILED / ACTIVE state badge that triggers the moment a
  rule is breached (with the exact breach reason and timestamp logged).

## MULTI-ACCOUNT (must work as described)
- I can create N accounts, each with its own rule set and its own balance/state, and give them names/colors.
- While replaying a single session I can switch the ACTIVE account at any time (dropdown + number hotkeys
  1-9) and place trades on whichever account is active — emulating trading the same live session across
  multiple prop accounts with different rules.
- Optional "mirror mode": place one trade and it executes on a selected subset of accounts simultaneously,
  auto-sizing each account per its own risk settings.
- All accounts track independently and continuously: balance, equity curve, drawdown floor, days traded,
  consistency, pass/fail. Switching accounts must NOT reset or pause the others' state.
- Accounts panel showing every account side by side with live balance, distance to floor, distance to
  target, and status.

## PRESETS & PERSISTENCE (drag-drop + download)
- Save/load a firm rule set as a `.json` preset: download button, and drag-drop a .json onto the app to load.
- Ship these built-in presets (I can edit them): Apex 50K (target +$3,000, $2,500 intraday trailing, no
  daily limit, 50% consistency, no min days), Apex 100K (+$6,000 / $3,000 intraday trailing / 50%
  consistency), TopStep 50K (+$3,000, $2,000 EOD trailing with lock at start, $1,000 daily limit),
  FTMO 15K 1-step (+10%, 10% static, 3% daily, 50% consistency, 4 min days), Goat Blitz 10K (+3%, 5% max
  loss, 3% daily). Mark clearly in the UI that preset numbers are user-verifiable defaults, not gospel.
- Save/load an entire SESSION (accounts + trades + drawings + replay position) to a .json file.

## STATS
- Per account and combined: net $, win rate, avg win / avg loss (in R and $), expectancy per trade, profit
  factor, max drawdown, longest win/loss streak, trades per day, best/worst day, days traded, and an
  equity curve chart.
- Exit-reason breakdown (TP / SL / manual / EOD) and an R-multiple histogram.
- Export all trades to CSV.

## UI LAYOUT
Left vertical toolbar (drawing tools), top bar (instrument, timeframe fixed at 1m, timezone, replay
controls, active-account selector), right panel (tabs: Accounts / Rules / Trades / Stats), bottom strip
(replay timeline scrubber). Keyboard shortcuts listed in a help overlay (press ?).

## BUILD ORDER
1. Data loader + IndexedDB cache + canvas candle renderer with pan/zoom/crosshair.
2. Replay engine with strict no-look-ahead + session lines.
3. Position/drawing tools with drag handles.
4. Trading + fill realism + trade log.
5. Prop rule engine (all three drawdown modes) + live HUD.
6. Multi-account switching + accounts panel.
7. Presets, session save/load, stats, CSV export.
Do them in that order and tell me when each is working. Keep the whole thing in one file, plain
JavaScript, no frameworks. Prioritize correctness of the drawdown/rule engine over visual polish — if
something must be approximated, tell me explicitly rather than silently faking it.
```
