# Published gold scalper execution feasibility

Source inspected: https://www.tradingview.com/script/braXKo74-Gold-Spread-Algo/

The author describes XAUUSD M1 RSI14 entries below 30 or above 70, a price-distance stop of $0.05, and a target of $0.10. The source describes high-frequency behavior. No execution or win-rate claim was accepted from the page.

Checked master M15 cache beginning with the loader's warmup before 2019 and ending before 2026: 178,093 bars, 81,481 with a positive recorded spread and 96,612 using the explicit 260-point fallback. All modeled spreads were greater than $0.05, with a median of $0.26. These are bar snapshots and cannot reconstruct the full intraminute spread path.

For a market buy at bid $2,000 / ask $2,000.26, a stop $0.05 below entry is $2,000.21, already above the bid. For a market sell at $2,000, the stop at $2,000.05 is below the current ask. Under that interpretation the intended stop begins on the wrong side of the exit quote. A request can be invalid, or a price-level implementation can encounter an immediate stop condition. Adding a larger stop would change the published rule.

This rejects a faithful transfer to the cached broker-cost scenario before portfolio and payout testing. It does not establish the quote conditions of every broker. The source's frequent short-duration exits also require separate funded minimum-hold and prohibited-practice review for Atlas.

The other inspected source, PowerTrend Pro – Gold Optimized (https://www.tradingview.com/script/VrdATmT4-PowerTrend-Pro-Strategy-Gold-Optimized/), lists VWAP, Supertrend, RSI and moving averages, but retrieved text did not expose all numerical presets, timing, stop, trailing and break-even conditions. Its claimed performance remains unverified. No invented replication was run.
