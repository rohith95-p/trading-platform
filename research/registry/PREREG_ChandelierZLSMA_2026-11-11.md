# Public Chandelier + ZLSMA transfer to XAUUSD

Registered before P&L execution. Source: geraked/tradingview strategies/CEZLSMA.pine,
frozen source and commit under research/sources/chandelier_zlsma. MIT source credits
Geraked and Rabist, links YouTube 2U5VTWBBK8U. Video could not be fetched; code, not
video interpretation, is the specification. Advertised PF5.392 concerns roughly ten
days of EURJPY M1, not gold. No claim to reproduce that result.

Fixed four variants: M1 and M5, each Heikin-Ashi signal OHLC and ordinary-candle
ablation. Source defaults ATR1, multiplier2, ZLSMA50 (2*LSMA50-LSMA50(LSMA50)).
CE flip filtered by signal close above/below ZLSMA; close existing long/short when
signal close crosses below/above ZLSMA. Entry/reversal next actual M1 opening after
signal candle close. Stop is CE stop at qualifying entry signal, not an automatically
trailing stop: source only submits strategy.exit inside entry signal blocks. A later
same-side qualifying signal can update that stop even with pyramiding disabled.

No Heikin-Ashi execution prices. Use actual bid OHLC for fills/stops; historical
spread/fallback.26, .02 slip, .07 roundtrip commission per .02lot, project funding.
Fixed .02lot, one position per isolated variant, no reentry unless fresh qualifying
signal, close at independent sample boundary. Initial stop wrong-side at opening
fills immediately at opening liquidation quote (record count), rather than dropping
an unfavorable trade. Such stops would require a live broker-specific handling rule.

Use frozen Genesis M1/M5 2013/2018/2025 samples for first screen; these are inspected
development years. Split >7day missing gaps into separate samples, renew 300 signal-
bar warmup after gaps; first sample has frozen pre-year warmup. No missing price
interpolation or synthetic equity-account claims. Minute-open equity, static first
stop path, timestamp/cash assertions, test indicator causality and actual fills.
No parameter optimization. PF>=1.3 and>=30 trades in every year advances to broader
years, independent forward data, risk sizing and Atlas/payout checks; not deployment.

Supplemental data-source sensitivity after original-snapshot outputs: fetch a separate
Dukascopy bid/ask2025 snapshot with December2024 warmup, without mixing providers or
selecting dates. Same four fixed rules/parameters, but observed ask OHLC determines
long entries and short exits/stops. Cost/funding settings otherwise unchanged. This
is a source/execution diagnostic on an already-inspected year, not new OOS data.
