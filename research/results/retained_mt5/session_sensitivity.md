# Native MT5 calendar sensitivity on 5 May 2026

A London Momentum Tight buy entered at 12:15:00.046 UTC in both implementations. MT5 bought at 4,565.070 with SL 4,549.812 and TP 4,595.586. The Python replay added $0.02 of modeled entry slippage, buying at 4,565.090 with SL 4,549.832 and TP 4,595.606.

The read-only SessionProbe EA ran in native MT5 on the same custom symbol, with real ticks. It observed all 15,605 archived quotes between 21:00 and 23:58 UTC. From 22:07:20.217 through 22:52:15.190, 2,073 bids were at or below the lower native stop. The minimum quote in the probe window was 4,546.188.

The custom symbol's native Tuesday trade and quote sessions are 00:00–21:58 and 23:00–24:00 UTC. The entire sequence of quotes crossing the native stop was outside that execution session. Native MT5 subsequently filled the TP at 4,595.593 and recorded +$61.05. The ordered-quote Python replay assumed these archived quotes were executable, triggered its SL at the first crossing, and recorded −$30.89. This one difference accounts for $91.94 of the $107.20 gap between the two unconditional 2026 portfolio profit figures.

These native session settings describe the November-cloned symbol used by the test. Historical Atlas-specific execution availability on the May date remains unknown. Both findings therefore belong in the interpretation of raw profitability. The test is not a validated backfill of Atlas dealing hours.

[Native probe output](native_session_probe_20260505.csv) · [Independent probe EA](../../mt5_retained/SessionProbe.mq5) · [Native/Python entry comparison](entry_parity.json)
