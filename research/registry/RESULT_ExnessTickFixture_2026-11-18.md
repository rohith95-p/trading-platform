# Two historical XAUUSD quote paths compared with the minute engine

Protocol `7f4e227` fixed both orders and the hour before downloading the Exness Raw Spread archive. The January 2025 ZIP passed CRC verification. Its 4,586,547 rows included 8,991 bid/ask updates on January 6 between 12:00 and 13:00 UTC. Six updates shared a millisecond with the previous quote. Source order was preserved. The largest interval between updates was 5.322 seconds. Median spread was $0.043 per ounce. [Exness tick history](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history)

| Diagnostic order, 0.02 lots | Ordered quote net P&L | Minute engine net P&L | Maximum drawdown on quotes | Maximum drawdown on minute samples |
| --- | ---: | ---: | ---: | ---: |
| Buy at 12:15 UTC | −$2.122 | −$2.110 | $5.042 | $3.616 |
| Sell at 12:30 UTC | −$2.228 | −$2.110 | $2.876 | $2.332 |

Both engines entered at the same price and identified the same stop exit in both cases. The minute labels preceded the observed crossing by 12.588 and 21.886 seconds. Both minute-level loss estimates were smaller. Timing and price differences matter near a drawdown floor even when the outcome is recorded as a stop in both replays.

The archive contains public historical Exness quotes. Each execution price is hypothetical under a fixed slip and commission assumption. Actual fills, Atlas prices and strategy profitability remain unverified. The JSON field `historical_verification` belongs to the shared fixture runner and remains false by design. Its provider, archive hash, quote-array hash and verification scope identify this historical feed.

Download the URL in `research/results/exness_tick_fixture_2026-11-18/comparison.json` and run `python -m scripts.validation.exness_tick_fixture <archive.zip> <new-result.json>`. The runner checks the frozen archive hash and refuses to overwrite an existing result.
