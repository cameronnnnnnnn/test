# FairPriceStrategy — "fair pricing theory" (video strategy), implemented and tested honestly

Source: video transcription (US$1.2M-payouts claim). Core thesis: the candle before a session
open is the session's **fair price**; the post-open move is "unfair" (new participants/opening
flow), so trade **continuation** of the opening candle for the first 0–10 min, then **reversion
back to the fair price** from 10–90 min. Entries = **displacement candle** (body > prior body,
tiny wicks) or **break of structure + close beyond** (fractal swings). A+ = both triggers.
Fixed **25pt stop / 38pt target (1:1.5)**. Sessions (EST→EET server): 18:00→01:00 reopen,
20:00→03:00 Asia, 03:00→10:00 London, 08:30→15:30 news, 09:30→16:30 NY (primary), 14:00→21:00 PM.
Session discipline: first qualifying setup in phase 1, max 4 accepted/session, phase 2 halts
after its first loss, next trade only after the prior one exits.

`fairprice.py` implements all of it with configurable thresholds (no magic numbers) and applies
the video's own (correct) doctrine: judge it by the **FTMO pass rate**, not the equity curve.

## Results (NAS100 M1 2022-2025, 2pt round-turn, 70/30 train/test)

**Faithful spec (25/38, all sessions): fails.**
| | n | WR | expR train | expR test |
|---|---|---|---|---|
| ALL | 5,679 (7.4/day) | 40.4% | −0.098 | −0.050 |
| P1 continuation | 3,125 | ~42% | −0.078 | +0.011 |
| P2 reversion (the "fair price" core) | 2,554 | ~39% | **−0.124** | **−0.110** |
| FTMO MC | | | **8–11% pass, 77–82% blow** | |

WR needed to break even at 1:1.52 after cost ≈ 43%; realized 40–42%. The claimed 70–80% WR is
nowhere in the data. The reversion phase — the strategy's centerpiece — is decisively negative in
BOTH halves, consistent with every other mean-reversion-to-anchor test in this project
(equilibrium scan, VWAP fades, gap fills: the "price returns to fair" premise doesn't exist
tradeably on this instrument). The 25pt stop makes cost 0.08R/trade — at 7.4 trades/day that is
the exact low-RR/high-frequency death mode proven in `challengephaseHF`.

**Robustness grid (not a strawman):** stops 25/38, 40/60, 50/75 × {all, NY-only, P1-only, A+-only}:
everything ≤ 0EV except ONE cell — **NY-open A+ only (displacement AND structure-break together)**
at 40–50pt stops: +0.03/+0.07 (40/60) and +0.04/+0.09 (50/75), n≈190, ~0.25 trades/day. The
confluence entry at the primary session with humane stops has a thin real edge. Stacked on 52p it
adds ~+0.3pt (TE20 50.7→51.0) — negligible at its frequency. Not worth deploying.

## Verdict
- **The strategy as specified does not work here** — and, notably, the video itself predicts
  this: "if you were to trade it on a live account, it would probably break even." Our CFD
  measurement is exactly that (~0EV at best geometry, negative at spec). His claimed edge lives —
  if anywhere — in prop-firm-specific mechanics (trailing-drawdown futures evals, resets,
  40-account survivorship), not in the price action itself.
- The video's one genuinely correct and valuable idea is methodological: **backtest the pass
  rate, not the equity curve** — which is precisely this project's method.
- Caveats: our data is US100 CFD (not NQ futures order flow), no true news calendar (15:30 anchor
  fired daily), and discretionary chart-reading ("structure", grade judgment) is only
  approximated by fractal rules. Faithful, but an approximation of a discretionary process.
