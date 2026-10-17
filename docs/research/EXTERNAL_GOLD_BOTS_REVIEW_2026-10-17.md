# External Gold Bots Review (2026-10-17)

Method: read-only. Repo pages, commit pages and raw source files fetched through WebFetch. Nothing was cloned, downloaded or run.

Limitation: WebFetch returns a model-written summary of each page. It does not return raw text, so the "exact" values below are the fetcher's extraction of the source. Treat them as high-confidence but not byte-verified. Before any reuse, read the raw file by hand. Dates, star counts and similar figures are as shown on the page snapshot.

## 1. phatnomenal/blackXAU_AUTOMATED-BOT-TRADE (MQL5)

### What is in the repo
- The repo exists and is public. It holds two files: `README.md` and `blackXAU2.mq5`.
- The source is about 250 long lines (EA header v1.22, "Fixed").
- Stars 53, forks 25, watchers 2, 1 open issue, 1 open PR.
- License: none shown.
- 7 commits, all on 2025-10-12 by `phatnomenal`. The first is "Add files via upload" and the last is "Update README.md". It is a single-day dump with no history.

### Strategy as implemented
This differs from what the README implies.

- **Zone, ZoneMode 0 (default).** The zone is the previous D1 high and low, `iHigh/iLow(PERIOD_D1,1)`. The README says "first H4 candle". That is ZoneMode 1, and it is buggy: it indexes `h4Index+k`, which in MQL5 series reads older bars (before today), not the first N H4 bars of today. It also falls back to index 0 (the forming bar) if `iBarShift` returns -1. It is computed once, at the first tick of the day, before the day's H4 bars exist.
- **Breakout.** M5 bar at shift 1 (closed bar). A bullish breakout is a close above zone high after an open at or below it. The bar needs a body of at least `BreakoutBodyPct` 50 or a move of at least `BreakoutMinPoints` 200. The breakout arms a retest state that expires after `MaxWaitSeconds` 86400.
- **Retest entry.** It is checked only on the first tick of each new M5 bar. It enters when `bid <= zoneHigh`.
  - It sends a market `trade.Buy`, so the fill is at ask. `zoneHigh` is used only as the notional entry for SL and TP.
  - The EMA filter requires H1 EMA50 and EMA200 (shift 1) below the price. The price compared is `iClose(H1,0)`, the forming bar, so the check mixes shifts.
  - **Only the long branch is live.** The short branch is inside `/* */`. A short breakout still sets `breakoutDir=-1` and cancels a pending long. `ShortLotMultiplier` 0.5 is unused.
- **SL/TP.**
  - ATR mode is the default (`UseATRSizing` true, H1 ATR(14) at shift 1). SL = zoneHigh - 1.5 x ATR. TP = zoneHigh + 3.0 x ATR. Both are in price units, so `_Point` does not matter here.
  - Fallback mode: SL = breakout candle low, TP = zoneHigh + 1.5 x (zoneHigh - SL). This is the "1.5R" in the README.
  - No check that SL is below ask. A deep pullback can give a stop that is invalid or hit at once.
- **Units.** Points-based inputs are multiplied by `_Point`.
  - `TrailingStart` 200 and `TrailingStep` 100 are points. `BE_MovePoints` is 300. `BreakoutMinPoints` is 200.
  - On a 2-digit gold feed (`_Point`=0.01), 200 points = $2.00. On a 3-digit feed (0.001), 200 points = $0.20. The same defaults give a 10x different behaviour by broker.
  - `MaxSpreadPoints` 50 is $0.50 on 2-digit and $0.05 on 3-digit.
- **Trailing.**
  - Mode 0 trails at a fixed 200 start and 100 step. Mode 1 uses M15 ATR(14) x 1.5 from the forming bar (shift 0, so the value changes intrabar).
  - It manages every position on `_Symbol` regardless of magic number.
  - It is skipped outside the session and during news windows, because `OnTick` returns early.
  - It creates and releases an ATR handle on every update (inefficient).
- **Lot sizing.**
  - The code default is `Lots`=0.1. The README table says 0.01, so the README and code disagree.
  - Risk mode is `lot = balance*Risk%/100 / (distPoints*tickValue)`, with `distPoints=|entry-sl|/_Point`. This assumes tickSize==point. The lot is raised to the broker minimum even if that exceeds the risk target. There is no user cap.
- **Filters.**
  - Session: `UseSessionFilter` true, 07:00-22:00 server time. The comments say London/NY, but server time is not GMT.
  - Spread: 50 points.
  - News filter (see below).
  - `OnlyOnePosition` true.
- **Risk controls.** There is no daily loss limit, no equity stop, no max trades per day, no Friday close and no end-of-day close. Positions rely on the per-trade SL/TP. Outside the session positions are not managed at all.
- **News filter.**
  - Built-in `CalendarValueHistory`, +/-30 min around now, currency "USD" by substring, importance at least MODERATE.
  - It only blocks entries and trailing in the window. It does not close positions or widen stops.
  - Calendar data is not available in the strategy tester, so a backtest run with the filter on has no news filtering.
- **Order handling.** The `CTrade` return values for Buy and PositionModify are not checked. `waitingRetest` resets regardless of success. There is no retry.

### Backtest and live claims
- Claim: XAUUSD M5, Jan 2022 to Oct 2025, "Every tick", default parameters. The README gives words ("consistent execution, controlled drawdown, stable risk-adjusted returns") and screenshots only.
- Not disclosed: net profit, drawdown, profit factor, trade count, spread or commission model, tick data source, out-of-sample split.
- No live results. The disclaimer says "research and educational purposes only".
- The claim cannot be verified. The tester cannot reproduce the news filter, and the long-only logic makes any 2022-2025 gold result largely a beta test on a strong up-trend.

### Safety review
- No WebRequest, no `#import`, no DLL, no account lock, no obfuscation, and no eval equivalent. Code is readable.
- Issues: unchecked order results, magic-number-blind trailing, mixed shift 0/1 reads, broken ZoneMode 1, README/code mismatches (Lots), hard-coded magic 202503, long-only despite a "breakout" label.

### Prop-firm fit
- Per-trade SL exists, which is good. But SL = 1.5 x H1 ATR is roughly $12-25 on gold, so the code default 0.1 lot risks about $120-250 per trade. At 0.01 lot it is fine.
- No daily-loss or max-drawdown guard, so it cannot enforce firm limits by itself.
- The news filter is +/-30 min but does not manage open positions, and its dependency on the calendar is fragile.
- No martingale and no grid, so tail risk is capped per trade. The open risk is the SL gap at news.
- Hold times are long (ATR-based), so no minimum-hold issue.

### Verdict: TEST AS HYPOTHESIS (low priority). Do not reuse the code.
Reasoning:
- The concept (prior-day range break, retest, H1 EMA trend filter, 1:2 ATR SL/TP) is generic and cheap to test on our M1 engine. It overlaps our already-rejected or benched families (liq-sweep reversal HYP-070, D1 gate HYP-067).
- The published evidence is zero. The code has real bugs. It is long-only, so it will look good in a bull regime.
- If tested, run it on the 22-year archive with M1 execution, with costs and across eras, and with the short side restored.

---

## 2. 3aLaee/xauusd-trading-bot (Python, MetaTrader5)

### What is in the repo
- The repo exists and is public. Files: `.gitignore`, `LICENSE`, `README.md`, `bot.py`, `requirements.txt`. `bot.py` is about 181 lines.
- Stars 191, forks 49, watchers 6, 2 open issues. License: MIT. Topics: bot, forex, trading, tradingbot, xauusd.
- 17 commits, all by `3aLaee`. First "first commit" 2024-11-10, last "Update README.md" 2025-01-23.
- Most commit messages are "updates". One notable one is "add SL after placing order" (2024-11-13), so the first versions placed orders without a stop.

### Strategy as implemented
- **Data.** `mt5.copy_rates_from_pos(symbol, M1, 0, 50)`. Start position 0 includes the forming bar. The signal bar is `data.iloc[-1]`, the forming bar. Every indicator is computed on a bar that is still changing.
- **MACD.** 12/26/9. The buy condition is `(macd > signal) & (macd.shift(1) <= signal.shift(1))`. The sell condition is the mirror. A cross detected on the forming bar can flip within the minute, which is a repainting signal. This is a look-ahead problem on the forming bar.
- **Support/resistance.** Support = `low.tail(10).min()`, resistance = `high.tail(10).max()`. The window includes the current bar.
  - The sell condition is `close < resistance`. The buy condition is `close > support`. Because the window includes the current bar, both conditions are almost always true.
  - So the "breakout" filter is not a filter. The README's description ("price breaks the last resistance") does not match the code. The signal is effectively just a MACD cross of the forming bar.
- **Entry.** Market order at tick ask (buy) or bid (sell). No None check on the tick.
- **SL/TP.**
  - `SL = price -/+ STOP_LOSS_PIPS*PIP_SIZE`, `TP = price +/- TAKE_PROFIT_PIPS*PIP_SIZE`. Code defaults: `STOP_LOSS_PIPS` 15, `TAKE_PROFIT_PIPS` 10, `PIP_SIZE` 0.01.
  - So the default SL is $0.15 and TP is $0.10 on a price near 2000-4000. The README `.env` example uses `PIP_SIZE` 0.10, which gives SL $1.50 and TP $1.00. The two sources disagree.
  - The names say "pips" but they are price units. They are not related to broker point or digits. Prices are not rounded to symbol digits.
  - Either way, TP < SL (R:R 0.67), so it needs about 60% or more win rate before costs.
- **Spread vs targets.** Gold retail spread is usually $0.10-0.40. With a $0.10 TP and $0.15 SL at the code default, the spread alone is comparable to or larger than the target. The broker also enforces a minimum stop distance (stops level), and the order may be rejected. At the README setting ($1.00 TP), the spread still takes a large share of the edge.
- **Position management.**
  - No check for existing positions. `show_open_positions()` only logs.
  - The loop runs every 60 s with no cooldown. A persistent signal, or flips between buy and sell across consecutive checks, opens repeated and opposite orders. Position count is unbounded.
- **Lot sizing.** Fixed `LOT_SIZE` default 0.1 (README example also 0.1). No risk-based sizing.
- **Order sending.** `order_send` with `type_filling` IOC, `deviation` 20, `magic` 123456. It checks `retcode != DONE` and logs. There is no None check on the result (AttributeError if `order_send` returns None).
- **Filters.** None. No spread, session, news or drawdown filter. The only check is a one-time `SYMBOL_TRADE_MODE_DISABLED` at startup. There is no loop-level market-hours check.
- **Exits.** None other than SL/TP.

### Backtest and live claims
- None. There are no results, only "Better results are shown during the London session" with no data. The README says it is for educational use on demo.

### Safety review
- Credentials come from env variables via `dotenv` (`MT5_PASSWORD`), and none are hard-coded. The only network is the MT5 terminal. No eval or exec. `.gitignore` is present.
- Issues: forming-bar signals, no duplicate-order guard (stacking), no exposure cap, TP < SL, no spread or session filter, unrounded prices, README/code default mismatch, hard-coded magic 123456.

### Prop-firm fit: unfit
- The stacking-orders bug can multiply exposure to an unbounded size in a minute-by-minute loop. There is no daily-loss guard.
- M1 scalping with a $0.10-$1.00 target holds positions for seconds to minutes. Many firms ban or flag very short holds (often under 1-2 minutes) and high-frequency scalping.
- It trades through news. It has no news filter.

### Verdict: REJECT
Reasoning:
- It is a tutorial-grade script. The S/R "breakout" filter is vacuous, the signal is computed on the forming bar, and nothing stops stacked duplicates.
- The stop and target are smaller than a typical gold spread at the code defaults. There is nothing to reuse. A plain MACD cross on M1 is a well-known zero-edge signal after costs and it overlaps with what our M1 engine would already reject.
- The one useful lesson is negative: its failure modes (forming-bar signals, unbounded position count, pip-versus-price units) are the exact bugs our audit checklist should catch.

---

## 3. mad808/gold-scalper-mt5 (MQL5, "Gold_Sniper_Scalper" v16.30)

### What is in the repo
- The repo exists and is public. Files: `Gold_Sniper_Scalper.mq5` (about 550-600 lines), `LICENSE`, `README.md`.
- Stars 6, forks 1, watchers 0, 1 open issue. License: MIT.
- 6 commits, all by `mad808`. First "Initial commit" 2026-06-18, last "README.md file updated" 2026-06-24. The repo is one week old. The author's Upwork and Telegram links are in the profile (this reads as a product/marketing page).
- The header says "$20 Min Deposit". The order comments still say `TGS_v16.10`, so the version tag was not updated consistently.

### Strategy as implemented
- **Signal timeframe.** M5 (`SignalTF`), once per new bar at shift 1 (closed bar). This is correct.
- **First-entry trend.** EMA13 vs EMA34. The H1 EMA200 macro filter exists but is off by default.
- **First-entry RSI(14).** Dynamic RSI is on.
  - ADX < 25 (`AdxTrendThreshold`): BUY needs RSI <= 48, SELL needs RSI >= 52. This is an almost-always-true gate.
  - ADX >= 25: BUY needs RSI <= 30, SELL needs RSI >= 70.
  - The input names `RSIOverbought`/`RSIOversold` are used with inverted semantics relative to their comments.
- **First entry.** With multi-TP on (default), three positions open at once (TP1/TP2/TP3).
- **Grid.**
  - BUY adds when `bid <= lowestBuy - step*_Point`. SELL adds when `ask >= highestSell + step*_Point`.
  - Step: `GridStepPoints` 150 scaled by H1 ATR (`AtrStepMultiplier` 1.2), clamped to 120-400 points, times per-level multipliers 1.0/1.1/1.3/1.6/2.0. Effectively the clamp overrides the 150 input.
  - Max 8 levels per side (`MaxGridLevels` 8). The comment says "max 8" but nothing enforces an upper bound on the input.
  - Adds are blocked when ADX > 55 (`GridAdxBlockLimit`), margin level < 100% (`MinMarginLevelPct`), or within 10 s of the last add (`MinGridIntervalSeconds`).
  - Adds run every tick on live bid/ask.
- **Martingale sizing.**
  - Mode MULT (default): `lot = lastLot * 1.6`, at least `lastLot + step`, normalized. The 8th level is about 0.27 lot if the start is 0.01 (about 0.34 after per-step rounding). Cumulative basket is roughly 0.87 lot on a 0.01 start.
  - Mode SAFE: base x 1, 1, 2, 2, 3.
  - Cap: `HardLotCap` 5.00.
  - Auto-lot: `balance/60 * 0.01` (`AutoLotStep_USD` 60). At $20 this rounds up to the 0.01 minimum. At $6000 it gives 1.00 lot as the first position, and with a 1.6x multiplier that is 4.6 lots after three levels.
- **Targets.** Multi-TP is a 3-stage split, 40 points base and 30 points per step. After grid positions exist, the basket uses a smart trail: activates at 40 points profit (`TrailActivationPoints`), exits on a 15-point retrace (`TrailStepPoints`). `BasketTP_Points` is 40. `UseBasketTrailing` and `BasketTrailFloor` are unused.
- **Stops.**
  - **No per-position SL** (`SendOrder` passes sl=0, tp=0). Everything is virtual and software-checked in `OnTick`. If the EA, the terminal or the connection goes down, positions have no stop at the broker.
  - Basket SL: `UseBasketSL_USD` true, `BasketSL_USD` 5.00. This is a fixed dollar amount and is not scaled to lot size or balance.
  - Emergency close: `dynSL = balance*95/100`. It closes everything when buy + sell floating P/L <= -dynSL.
  - `MaxBasketTimeMinutes` 240 closes a side after 4 h.
- **Units.** Points x `_Point`. The comment "150 Puan = $1.50" is true only on a 2-digit feed. On a 3-digit feed 150 points = $0.15. So every point input changes meaning by 10x between brokers. The EA does not normalize for this.
- **News filter.** `CalendarValueHistory`, country "US", high importance, +/-15 min. It is off by default (`UseNewsFilter` false). When on, it blocks only the first entry, not grid adds, so a basket keeps averaging through news. Session filter is off by default (07:00-18:00 when on).
- **Spread.** `MaxSpreadPoints` 45 (about $0.45 on a 2-digit feed, $0.045 on a 3-digit).
- **Order handling.** Filling mode is chosen from the symbol's allowed modes. Closes retry up to 5 times with growing slippage. Errors are logged with retcode. This part is competently written.
- **Account type.** Assumes a hedging account. It does not check `ACCOUNT_MARGIN_MODE`. On a netting account the per-position logic would not work.
- **External code.** `#include <Trade\Trade.mqh>` only. No WebRequest, no DLL, no license check, no hard-coded account, no obfuscation.

### How the risk controls interact (my analysis; derived from the extracted parameters)
- The $5 basket SL is a fixed number while lots grow 1.6x per level. At a 0.01 start, the first grid add (150 points = $1.50 adverse on 3 positions at 0.01) already costs about $4.50 on the three 0.01 positions (3 x 0.01 lot x 100 oz x $1.50). A second grid level pushes the basket past -$5.
- So at $20 account size the $5 basket stop (25% of equity) closes the basket early. Result: a small win (40 points on 0.03 lot = about $1.20) versus a -$5 loss. The payoff ratio is about 0.24 to 1, so the system needs a win rate above about 80% before costs, and the "martingale" depth is cut off by the stop.
- At any larger balance, auto-lot scales the lot up while the $5 stop does not scale. The stop then fires almost immediately (a few cents of adverse move on a 0.87-lot basket). Changing the stop to scale with equity would let the grid run to depth and expose the full martingale tail up to the 95% backstop.
- Either way the system has two bad modes: a high win rate with small gains, and rare large losses. The README (8 levels, "no blown accounts") says it protects the account, but it does not demonstrate this.

### Backtest and live claims
- None. There are no win rate, drawdown, profit factor, data source or cost figures, and no out-of-sample test. The README markets it for accounts "starting from $20" and warns that martingale can lose the entire deposit.

### Safety review
- Clean of obfuscation, network calls and credentials.
- Real issues: no broker-side SL, a fixed-dollar basket SL, an unbounded martingale on auto-lot, a 95% drawdown floor, 10x unit ambiguity by broker digits, news filter off by default and not covering grid adds, hedging-only assumption, inverted RSI input names, unused inputs, version tag drift, and a "$20 minimum" claim that is marketing rather than risk-managed.

### Prop-firm fit: unfit
- Martingale and grid averaging are banned or restricted by most firms, and the stop is software-only.
- Floating-loss exposure exceeds typical daily drawdown limits (about 4-5%) quickly. Simultaneous opposite-side baskets (hedging) are also disallowed at many firms.
- Trailing-drawdown or static-drawdown accounts get breached by one adverse basket. The 95% emergency floor is meaningless against a 5-10% limit.
- Positions held for 40-point targets are often under the minimum hold time of some firms.

### Verdict: REJECT
Reasoning:
- It contradicts our mission directly. The mission is a survivable 0.01-lot system on a $100 account, and martingale-grid has a bounded win and unbounded tail by construction.
- There is no evidence at all. The only part with any value is engineering hygiene (filling-mode selection, retry-close, margin-level guard, ATR-scaled spacing), which is trivial to rewrite.

---

## Summary table

| # | Repo | Language / size | Stars / forks / license | Commits (first - last) | Core logic | Evidence disclosed | Main red flags | Prop-firm | Verdict |
|---|------|-----------------|--------------------------|------------------------|-----------|-------------------|----------------|-----------|---------|
| 1 | phatnomenal/blackXAU_AUTOMATED-BOT-TRADE | MQL5, about 250 lines + README | 53 / 25 / none shown | 7 (2025-10-12 same day) | Prev-D1 range break (README says H4), M5 retest, long only, ATR 1.5/3.0 SL/TP, H1 EMA50/200 | Screenshots only, no numbers, no OOS | Short side commented out, ZoneMode 1 bug, unchecked order results, README/code lot mismatch | Per-trade SL, no martingale; no DD guard | Test as hypothesis (low priority); do not reuse code |
| 2 | 3aLaee/xauusd-trading-bot | Python, about 181 lines | 191 / 49 / MIT | 17 (2024-11-10 to 2025-01-23) | M1 MACD 12/26/9 cross on forming bar + vacuous 10-bar S/R | None | Forming-bar signal, no duplicate guard, TP < SL, SL/TP $0.15/$0.10 vs spread | Unfit (stacking, scalping, no news filter) | Reject |
| 3 | mad808/gold-scalper-mt5 | MQL5, about 550-600 lines | 6 / 1 / MIT | 6 (2026-06-18 to 2026-06-24) | M5 EMA13/34 + dynamic RSI, 1.6x martingale grid up to 8 levels, 3-way multi-TP | None | No broker SL, fixed $5 basket stop, 95% DD floor, 10x unit ambiguity, hedging only | Unfit (martingale, hedging, software-only stops) | Reject |
