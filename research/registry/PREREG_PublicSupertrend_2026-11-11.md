# Published Supertrend reversal transfer

Official rule source https://www.tradingview.com/support/solutions/43000645068-supertrend-strategy/ and calculation https://www.tradingview.com/support/solutions/43000634738-supertrend/

Gold-only transfer: ATR10 Wilder SMA seed, factor3. Two predefined timeframes H1/H4. Long on bearish-to-bullish band flip, short on reverse, next bar open. Fixed protective stop three entry ATR away; opposite flip closes/reverses, no target. One position, fixed .02 lots; gap-aware stop fills, ECN spread/commission/slippage/swap. Existing archived SupertrendEMA is a different implementation with an EMA filter; generic Supertrend combinations previously failed and count in the search history. This reproduction tests the official plain reversal rule with a defined stop. Stop resolution on aggregate OHLC with no intrabar target competing is a preliminary screen. Fixed eras 2005–11, 2012–18, 2019–2025. No tuning. PF gates unchanged.
