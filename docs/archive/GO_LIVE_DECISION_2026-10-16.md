# Go-live decision pack: demo forward test, 24 Aug - 15 Oct 2026

Written 2026-10-16. Account: Exness **DEMO** #198874999, server Exness-MT5Trial11, XAUUSDm, 0.01 lot per trade.
This is not real money, whatever any older document says. Times are IST. Money figures are US dollars.
Authoritative source: MT5 deal history (broker). The bot's own logs are used only for the *why*, because they are incomplete (section 5).

## 1. Verdict

- **The sample is too small to prove an edge.** 34 trades under the current system (V5, since 28 Sep) over 9 trading days. Net +$6.13.
- **It is roughly breakeven, and that is the honest reading.** All 85 trades since 24 Aug: net +$34.36, profit factor 1.09, 40% wins. Current system: PF 1.11, 21% wins.
  Profit factor is total money won divided by total money lost; 1.00 is breakeven. The 21% win rate sits inside its own error band (about 10% to 37%) around the 25% this stop/target shape needs to break even.
- **TrendPullback is the losing leg** (14 trades, -$20.13, PF 0.33) and it is the leg that trades most. FVG is the only leg with a real profit (+$27.59), earned by 4 winners out of 13.
- **The profit is fragile.** Best single day (5 Oct, +$18.12) is 43% of all positive profit. Remove that day and V5 is about -$12. Remove the two best trades (+$12.24, +$10.49) and it is about -$17.
- **One market regime only.** The daily trend filter read BEARISH on every logged day from 7 Sep to 14 Oct, so almost every trade was a sell. Nothing here shows how the bot behaves in an uptrend. The only buys (15 Oct, after a filter flip) lost twice.
- **Reliability is not proven.** About 20 hours (possibly longer) with the bot down and no alert on 14-15 Oct; two whole weeks (14 Sep, 21 Sep) with zero trades.
- **Backtests do not rescue it.** The 16 Oct deep audit (`docs/DEEP_AUDIT_2026-10-16.md` s2.1, s6) re-ran the same 4 legs with a corrected engine: PF 0.88 over 4 years, 0.93 on one-minute data. Live (about 1.1) is consistent with "breakeven, give or take noise".
- My read: this evidence does not support going live on a prop account this week. The decision is yours; section 7 lists what would change the answer.

## 2. Headline numbers (broker)

| Period | Trades | Net | PF | Win % | Worst closed-trade drawdown |
|---|---|---|---|---|---|
| 24 Aug - 15 Oct, older + V5 portfolios | 85 | +$34.36 | 1.09 | 40% | $87 |
| V5 era only (magic 5000+, 28 Sep - 15 Oct) | 34 | +$6.13 | 1.11 | 21% | $16.35 |
| Older portfolios only (derived: 85-34, 34.36-6.13) | 51 | +$28.23 | n/a | n/a | n/a |

Rough significance check for V5 (my arithmetic): average +$0.18 per trade, typical spread of trade results about $4.8, so the average is only ~0.2 standard errors above zero. Statistically indistinguishable from nothing.
Caveat on the older +$28.23: about $22 of the 2 Sep profit came from three oversized 0.02-0.03 lot trades (sizing bug, fixed that day; `docs/trade_logs/STATUS_2026-09-06.md`). At the intended 0.01 lot it would be lower.
Balance trail reconciles: $142.91 (24 Aug) + $34.36 = $177.27 (15 Oct close). The demo balance reset on 22 Aug (deposit $10,000 / withdraw $9,900) is before this window.

## 3. By week (broker net)

| Week starting | Net | Trades | What was running / what happened |
|---|---|---|---|
| 24 Aug | +$48.31 | n/a | Legacy multi-strategy bot (magic 2xxx), retired 31 Aug. |
| 31 Aug | -$62.29 | n/a | Legacy bot lost heavily to 31 Aug (MORNING_MOMENTUM about -$118 over 28-31 Aug, straddles two weeks); portfolio_v4 from 1 Sep; 2 Sep oversize-lot wins; 3 Sep EMASTACK -$6.83. |
| 7 Sep | +$42.21 | n/a | portfolio_v4 (EMASTACK London + FVG legs, 30xx magics). |
| 14 Sep | $0 | 0 | Idle. Logs show only gate-blocked signals (16 Sep). |
| 21 Sep | $0 | 0 | Idle. Logs show only gate-blocked signals (21 Sep). |
| 28 Sep | -$16.56 | 15 | First V5 week, **0.1x ATR stops** (about $1 per loss). 28 Sep: 8 of 8 lost (-$7.90). 30 Sep: 2 PDHLR losses. 2 Oct: 5 losses (-$6.80), bot halted by hand 23:17 ("done for the week"). No winner recorded. |
| 5 Oct | +$20.63 | 11 | Stops widened to 0.5x ATR / target 1.5x. 5 Oct +$18.12, 6 Oct +$13.14, 7 Oct -$10.63, 8-9 Oct no trades. |
| 12 Oct (incomplete) | +$2.06 | 8 | 12 Oct -$0.20, 13 Oct +$11.13, 14 Oct bot down, 15 Oct -$8.87. |

Sum: 48.31 - 62.29 + 42.21 - 16.56 + 20.63 + 2.06 = +34.36. Weekly trade counts for V5 weeks are derived from alerts/daily reports and add to the broker's 34.

## 4. By strategy (V5 era, broker, by magic)

| Leg (magic) | Trades | Net | PF | What the files show |
|---|---|---|---|---|
| TREND_PULLBACK (5001) | 14 | -$20.13 | 0.33 | 2 winners (+$8.49 12 Oct, +$1.49 13 Oct). 12 losers: 5 tiny-stop on 28 Sep (-$4.65), 3 on 7 Oct (-$10.63), 2 on 12 Oct, 2 counter-trend buys on 15 Oct (-$8.87). |
| FVG_NY_TIGHT (5005) | 13 | +$27.59 | 2.85 | 4 winners +$42.53 (10.49, 12.24, 10.16, 9.64); 9 losers -$14.94. Without the best winner still +$15. |
| PDHLR (5008) | 6 | -$10.55 | 0 | All 6 lost. Retired 13 Oct (`docs/DECISIONS.md`). |
| BB_MEAN_REVERSION (5002) | 1 | +$9.22 | n/a | One trade (6 Oct). Its buy signals were blocked by the BEARISH filter nearly every day. |
| NVMR (5003) | 0 | $0 | n/a | Never traded; every logged signal was blocked by the BEARISH filter. |

Both of the profitable legs are tiny samples (4 and 1 winners). Two of the four live legs have effectively not been tested at all.

## 5. Incidents that cost trades or distorted results (each checked against files)

| Date | Claim | Verified? | Effect / source |
|---|---|---|---|
| 7 Oct | "Dedup bug blocked signals for 3+ hours" | **Not supported.** | `logs/trades/2026-10-07.jsonl`: "deduped" rows repeat only within one 15-minute candle (normal, seen every day); every new candle produced a new order (17:45, 18:01, 18:15). The log then stops at 18:18. Matching cause: daily-loss shutdown (shadow gate printed "daily loss 3.6% >= 3% cap" at 18:15; `main_loop.py` ~L349-359 sets `drawdown_shutdown`). Claimed "fix at main_loop.py line 442" is not where the stale-key clearing lives (L460-466). Evening signals lost either way, count unknown. Source: `daily_trade_progress/2026-10-07_Wednesday.md`. |
| 7 Oct | Day P&L | Corrected | Three losses -2.80, -3.95 (never logged), -3.88 = -$10.63 (balance 185.84 -> 175.21, `logs/alerts.log`). Report says "2 confirmed". |
| 14-15 Oct | Bot down about 20 h, no alert | **Verified, possibly worse.** | `alerts.log`: nothing from 14 Oct 22:24 to 15 Oct 18:23. `main_loop.log` is also silent from 13 Oct 22:42 to 14 Oct 22:24, and `logs/trades/2026-10-14.jsonl` has no real signals, so all of 14 Oct may be lost too (not proven). Hourly audits meanwhile said "ACTIVE & HEALTHY". Deep audit s2.5: scheduled task failed (0x800710E0), PC sleep suspected. |
| 15 Oct | D1 filter flipped to BULLISH intraday | **Verified (trade log); cause inferred.** | Same minute pair: BUY "blocked, BEARISH" 20:19:24, then BUY order 20:20:41. Two buys, both stopped, -$4.43 and -$4.44. 15 rows of "D1 bias gate (BULLISH)" that day, none on any earlier day. Code: `main_loop.py` L409-437 (override at 1.0x range; deep audit says this was tightened from 2.0x, uncommitted). The main_loop.log line is missing, so the flip itself is inferred. |
| 28 Sep - 5 Oct | 0.1x ATR stops | **Verified.** | 16 orders with 0.1x ATR stop in the logs (all 28 Sep, 30 Sep, 2 Oct, first 5 Oct trade, -$0.71). Declared "retired" only in the 13 Oct DECISIONS row. These trades are in the V5 numbers above. |
| 2 Oct, 6 Oct, 7 Oct | Risk caps (5 losses, 2 losses/day, 3% day) | Shadow only. | Log field `enforced:false` until at least 7 Oct; orders were sent anyway (2 Oct x3, 6 Oct x2 incl. a +$10.16 winner, 7 Oct x1). `enforced:true` from 12 Oct. `DECISIONS.md` says enforcement started 17 Sep: contradicted. |
| 12 Oct | 2-loss/day cap | Counter undercounted | First loss (FVG -$2.73, 18:16) was never logged as closed, so the counter read 1 loss at the 21:00 entry. Daily report says +$2.53; real day was -$0.20 (175.21 -> 175.01). |
| 15 Oct | 2 losses/day cap | Verified | Two losses, `day_losing_trades` 2, day over (enforced). |
| 13-15 Oct | Test orders in live log | Verified | 17 `TEST_STRATEGY` rows (price 2652.5, ticket 99901) in `logs/trades/2026-10-13/14/15.jsonl`; fake "CIRCUIT BREAKER TRIPPED" alerts on 28 Sep, 9 Oct, 11 Oct. Not real trades; ignore when counting shutdowns. |

## 6. Where documents disagree with the broker or with each other

- `docs/trade_logs/LIVE_TRADE_HISTORY.md`: says **"Account: Real"** (it is demo) and that 28 Sep trades "went LONG". Order log says all 28 Sep orders were SELL (its own exit prices sit above entry). Stale since 30 Sep.
- `daily_trade_progress/` reports are built from the bot log and miss trades. 5 Oct: omits the -$0.71 trade, labels the +$12.24 ticket 684256150 TREND_PULLBACK (alerts say FVG), start/end balances wrong (end shows 6 Oct's $185.84). 12 Oct: +$2.53 vs real -$0.20. 7 Oct: see above.
- `docs/DEEP_AUDIT_2026-10-16.md` s2.3: "22 closed trades, +$23, PF 1.6" is from the incomplete log. Broker: 34 trades, +$6.13, PF 1.11. About $17 of losses are missing from the log (22 logged closes vs 34 real trades).
- `README.md`: "Recent Live Holdout 3-14 Oct, PF 2.018" is a backtest, not live. README also says max 1 position; code and DECISIONS say 2.
- `reports/LAST_WEEK_ANALYSIS_AND_RISK_ASSESSMENT.md` (3 Oct): says 5 trades, ~$5-10 loss; broker week was 15 trades, -$16.56. Quotes PF 3.318, max drawdown 1.48%, $154 account, 0.015-0.020 lots, and tells you to trade the "0.1/2.0 configuration". Real lots 0.01, 0.1 stops retired, backtest PF later re-measured at ~0.9. Do not use.
- `docs/DECISIONS.md`: enforcement date (above); "daily loss limit 6%" while the live gate printed 3%; retirement of 0.1 stops dated 13 Oct but live orders changed on 5 Oct.
- Trade log `lots` field says 0.02; actual fills were 0.01 (Telegram trade alerts, hourly audit deals).
- Alert balances are unreliable: 17 Sep "Balance $187.70" and 9 Oct "$185.84" do not fit the broker trail (171.14 and 175.21).
- `docs/trade_logs/STATUS_2026-09-06.md`, `docs/research/BACKTEST_VS_LIVE_ANALYSIS.md` (Aug), `docs/research/REAL_MONEY_READINESS*.md` (Sep 2026 plans, go-live 30 Sep): describe superseded portfolios and dates; read as history only.

## 7. What would change the answer

- A clean, uninterrupted run (the deep audit asks for at least 8 weeks) with every trade counted from the broker, not from the bot log. V5 has run only 3 weeks (the first with the since-retired 0.1x stops), and the last week was partly down.
- At least one stretch where the trend filter is BULLISH, so the sell-only result is not the whole story.
- TrendPullback fixed or benched, and the D1 intraday override either tested or switched off.
- The scheduler/uptime problem solved, so downtime does not silently skip sessions.
- Prop-firm rules checked (`docs/PROP_FIRM_DUE_DILIGENCE.md`): daily and max loss limits, bots allowed, minimum hold time. At 0.01 lot the demo has never been tested at prop-account size, where slippage and drawdown limits bite harder.

## 8. Method

Read: `daily_trade_progress/*.md`, `docs/trade_logs/*.md`, `logs/trades/*.jsonl` (every day), `logs/alerts.log`, `logs/main_loop.log`, `logs/risk_state.json`, `logs/loop_state.json`, `reports/LAST_WEEK_ANALYSIS_AND_RISK_ASSESSMENT.md`, `docs/DECISIONS.md`, `docs/DEEP_AUDIT_2026-10-16.md`, README. No code, logs, state or credentials were changed. Broker figures (weekly, by-magic) were supplied from MT5 deal history and not re-queried; they cross-check against the log-derived daily results to within the unlogged trades noted above.
