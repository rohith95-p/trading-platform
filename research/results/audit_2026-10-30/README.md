# Independent audit of the live bot, 2026-10-30

Live setup audited: 5-leg Atlas portfolio, $5K, 0.02 lots per trade, max 3 open (3 per direction), profit protector
**off**, 24h entries, D1 gate, real `AtlasRuleEngine` guard (STOP_NEW blocks entries, FLATTEN closes all), costs =
`realistic_ecn` (bar spread, 20-point slippage on entries and stops, $3.50/lot commission, broker swap).

Re-run: `python scripts/validation/independent_audit_run.py` then `python scripts/validation/independent_audit_check.py`.

## 1. Does the engine compute what it claims? Yes
Step 2 re-derives every trade from the raw M1 bars with numpy, without engine code:

| Check | DEV (313) | TEST (270 M1) | RECENT (61) |
|---|---|---|---|
| P&L = (exit − entry) × side × lots × 100 | 0 mismatches | 0 | 0 |
| Commission, swap (nights × −515.5 pts on longs) | 0 | 0 | 0 |
| Exit on the first M1 bar that touches stop/target (spread-adjusted for shorts) | 0 | 0 | 0 |
| Exit price = stop − slippage or target | 0 | 0 | 0 |
| No earlier stop/target touch missed before a Friday close | 0 | 0 | 0 |
| Running balance chain | 0 | 0 | 0 |
| Stop gapped through (real fill worse than modelled) | 1 trade, $0.01 | 1 trade, $0.11 | 0 |
| Trades on coarse M15 bars (data hole), excluded | 0 | 21 | 0 |

Look-ahead probe: the RECENT window replayed only up to 2026-09-15 gives the identical 37 trades (same entries,
stops, targets, exits) as the full run, so no trade used data from after its own time.

## 2. Problems found
1. **M1 data hole, 2025-09-12 → 2025-10-15.** For that month the engine silently fell back to M15 bars (coarse,
   known to be optimistic). Those 21 trades had PF 2.09 and inflated TEST from PF 1.32 to 1.38. Numbers below exclude it.
2. **Atlas daily reference after a big giveback.** Atlas measures today's loss from *yesterday's highest equity*.
   On 2025-11-21 an open trade was +$240 at its best and then gave it back; the next session opened with 97% of the $250
   daily allowance already used and the guard flattened (no trades were open). Live, that also latches a halt
   that only a manual `halt clear` removes; the backtest resumes the next day. More likely with the protector off.
   Owner decision pending.
3. **Live allows 3 trades in the same direction, research used 2.** Immaterial: 1 extra trade in 4 years.
4. **Alerts:** the Friday close was sent as a CRITICAL "KILL SWITCH"; an Atlas flatten sent 3 CRITICALs; a halt
   made the watchdog restart a bot that refuses to start (alert loop, then watchdog exit); every boot sent a false
   "protect_profit NOT running" WARN; a slow MT5 start could be killed as "hung". All fixed in this change.

## 3. Results (M1 bars only)
| Window | Trades | Net | PF (90% CI) | Win rate | P(edge > 0) | Median month | Losing months | Max DD | Longest losing run |
|---|---|---|---|---|---|---|---|---|---|
| DEV 2022-08 → 2024-06 | 313 | +$130 | 1.07 (0.87–1.33) | 37% | 0.71 | +$11 | 37% | $209 | 9 |
| TEST 2024-06 → 2026-02 | 270 | +$885 | 1.32 (1.04–1.67) | 38% | 0.97 | +$32 | 42% | $272 | 11 |
| RECENT 2026-07 → 2026-10 | 61 | +$611 | 1.53 (0.97–2.37) | 44% | 0.94 | +$187 | 25% | $269 | 5 |
| Pooled | 644 | +$1,627 | (1.09–1.52) | | 0.99 (t = 2.42) | | | | |

Per strategy (pooled): NY Session Reversal +$643 PF 1.35 · London Momentum Tight +$398 PF 1.21 · Asian Range Filtered
+$393 PF 1.39 · Asian Breakout +$204 PF 2.28 (23 trades) · **Donchian Trend −$11 PF 0.98** (RECENT PF 0.34).

Caveats: these 5 legs were chosen from about 100 screened strategies partly on these windows, so the true
out-of-sample edge is weaker than the pooled bootstrap suggests; DEV on its own is break-even. The live forward test
of this exact setup has no trades yet (started 2026-10-27/29).
