# Daily Monitoring Ritual: Live vs Backtest Drift

To ensure Ultra Core v3 operates safely in production and matches our backtested expectations, perform this ritual daily.

## 1. The Morning Audit (08:00 IST)
Before the London session opens, review the output from the `send_daily_report()` job:
- **Realised P/L:** Ensure it matches the broker statement.
- **Trade Count:** Did the bot overtrade? (Compare against expected frequency for FVG legs).
- **Streak Breakers:** Did the `day_losing_trades` or `consecutive_losses` triggers fire correctly?

## 2. Reviewing the Logs (`logs/bot.log`)
Grep for warnings, errors, and blocked trades:
- **"blocked -- spread"**: Are spreads during NY session widening beyond the `max_spread_pts` (250) threshold? If so, the broker's liquidity may be shifting.
- **"blocked -- D1 bias"**: Verify that the EMA20 trend filter is correctly keeping us out of toxic counter-trend setups.
- **"VI.3 TRIPWIRE"**: Check the rolling 30-trade Profit Factor. If this fires (< 0.8), the bot will auto-halt via the kill switch. Do not restart without a full root-cause analysis.

## 3. Drift Analysis (Weekly - Saturday)
The live environment experiences slippage, spread variance, and tick-level noise that M15 backtests cannot perfectly simulate.
1. **Compare Executions:** Export the week's live MT5 deal history.
2. **Run Validation Replay:** Run `scripts/live_config_ab.py` or a standard backtest over the same 5-day window.
3. **Measure Variance:**
   - Are live entries consistently worse than backtest entries? (Slippage check)
   - Are live stops being triggered prematurely by spread spikes?
   - If Profit Factor drift exceeds -15% relative to the backtest, pause live trading and recalibrate ATR multipliers or investigate broker conditions.

## 4. Manual Kill Switch Drill
Ensure the `STOP` file mechanism is functional. Dropping a `STOP` file into the project root should immediately flatten all open positions and halt the `main_loop`. Validate this behavior in a demo environment monthly.
