# FairPriceStrategy — "fair pricing theory" (two video transcripts), tested honestly

v1 implemented the first transcript across all 6 sessions and failed hard (8-11% pass) — but the
user correctly called the implementation unfaithful. The second transcript fixed five real gaps:
fair price is the pre-open candle ZONE (not its close); **break-of-structure is THE reversion
entry** (displacement is a strength qualifier); **the adaptive stop rule** (trigger candle >25pts
→ 50pt stop / 76pt TP at half size, same $ risk); re-entry after losses is normal
(win-loss-win-loss-win); and scope = NY 9:30 only (no news calendar).

## v3 results (NY 9:30 only, faithful; NAS100 M1, 2pt cost, 70/30 train/test)
Overall: 1.87 trades/day, WR ~42%, expR **train −0.056 / test −0.001** — breakeven, exactly what
the video itself predicts outside prop-specific mechanics. FTMO MC standalone: 17% pass / 55-64%
blow. The REVERSION core (trade back to fair) is negative/flat in both halves in every cut —
consistent with every reversion-to-anchor test in this project.

**But the split found a real component.** The adaptive-stop rule cleanly separates the trades:
| slice | n | expR train | expR test |
|---|---|---|---|
| 25/38 trades (small trigger candle) | 987 | −0.088 | −0.107 |
| **50/76 trades (big trigger candle)** | 440 | **+0.050** | **+0.125** |
| ...of which **P1 continuation** | 265 | **+0.109** | **+0.178** |
| ...of which P2 reversion | 175 | −0.072 | +0.066 (flip) |

**The keeper: FP-s50-P1 — big-candle opening continuation.** First ~15 min after the NY open,
trigger candle (displacement or BOS+close in the opening candle's direction) with range >25pts,
50pt stop / 76pt TP (1:1.5), up to 2 entries. ~0.35 trades/day, +0.109/+0.178 both halves,
correlation with 52p only **+0.11** (candle-displacement fires on different days than the 15-min
range breakout).

## Stacking (risk on train, TEST reported)
| build | TE20 pass | blow | 40d pass |
|---|---|---|---|
| 52p | 50.7% | 30.9% | 67.7% |
| 52p + FP leg | 52.8% | 29.5% | 69.0% |
| 52pPlus | 54.5% | 28.2% | 69.5% |
| **52pPlus + FP leg** | **56.6%** | **27.0%** | **70.9%** |

**+2.1 points OOS on top of the full Plus, with lower blow — the largest single-leg addition
since turn-of-month, sourced from the user's video.** The fair-price REVERSION thesis still
doesn't survive on this data; what survives is the strategy's continuation entry + its adaptive
sizing rule, which concentrates the trades on high-energy opens and gives them room to breathe.

Caveats: US100 CFD (not NQ futures), fractal-rule approximation of discretionary structure
reading, no news-day handling. EA port of the FP leg (leg I) is straightforward: 16:30-16:45
window, opening-candle direction, trigger-range >25pts, 50/76, max 2 entries.

## Standalone deliverable — `FairPriceNY.py` (+ `standalone.py`, the build/search)
User scope: a standalone strategy, not a 52p add-on. Distilled to the honestly-surviving core:
NY-open **big-candle** (trigger range >25pts) continuation (first 15 min, ≤2 entries) + reversion
(BOS, ≥30pts room), 50pt stop, **hard 4R TP** (exit swept on train only — at 4R even the
reversion leg is +EV both halves; the video's 1.5R is this framework's weakest exit).

Edge: 0.64 trd/day · WR 36.3% · **expR +0.138** (per-trade better than 52p). Standalone ceiling
(risk-horizon map, ALL data): at **1% risk — 2mo ~27%/12% blow, 3mo ~39%/18%, 4.5mo ~51%/24%**;
at 0.75% it almost never blows but crawls; ≥1.25% risk destroys it (blow explodes). A relative
(vol-scaled) big-candle threshold was tested to add frequency: worse OOS; London leg has no edge
under either threshold. **The limit is structural: 0.64 trades/day of 4R shots cannot reach +10%
in 20-40 days at survivable risk — the frequency wall, not edge quality.** As a standalone it is
a patient, low-blow grinder well below 52p's pass curve (72% @ 2mo); its best use remains as an
edge-source (the FP leg lifts 52pPlus to 56.6% OOS — see above), but it stands on its own at the
numbers stated.

## User-spec version (`user_spec.py`) — and the reconciliation
The user's exact manual rules (0-1 continuation in 0-10min; 2-3 reversions with displacement-OR-
BOS triggers; TP-room rule: TP no more than 5pts past the FAR edge of the fair area; BE rule:
if TP reaches past the NEAR edge, breakeven on first touch of it; adaptive 25/38→50/76):
2.27 accepted trades/day (raw ~3.1 ≈ the user's manual 3-4).

**The zero-cost check reconciles everything:**
| | WR | expR train/test |
|---|---|---|
| zero cost (what a manual chart backtest sees) | 41-43% | **+0.009 / +0.029** (positive!) |
| real 2pt CFD spread | 40-42% | −0.064 / −0.036 |

The pattern is REAL on raw prices — the user's manual verification is correct — but at 25pt
stops the 2pt spread costs 0.08R/trade, 3-8x the raw edge. On US100 CFD the spec is therefore
net-negative (MC 8-13% pass). On NQ/MNQ futures (~0.5-0.75pt effective cost) it sits at ~0EV —
exactly matching the video's own "would break even live" and explaining his actual engine:
0EV edge + prop-firm convexity + dozens of accounts + resets. The only cost-viable CFD
expression of the framework is the big-candle/4R distillation (`FairPriceNY.py`).
