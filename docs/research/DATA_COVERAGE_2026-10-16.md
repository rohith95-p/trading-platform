# Data coverage, 2026-10-16

Broker-native MT5 history for the multi-asset study, cached in `research/data/<SYMBOL>_<TF>.npy` + `.manifest.json` (schema of `src/backtesting/data.py`: `DataManifest` + `SymbolSpec`, sha256 over the structured array). Server: Exness-MT5Trial11 (demo). Bar timestamps are broker server time as delivered by MT5. XAUUSDm files were not touched.

Spread columns are the bar `spread` field in **points** (value at bar open/close as recorded by MT5; `point` per the symbol table). Gap counts come from the manifest gap list (any inter-bar delta > 1 bar); a gap is labelled `weekend` by the pipeline when it starts Fri-Sun and exceeds 12h, so **all other gaps are counted as non-weekend** (this includes holidays such as Christmas/New Year, and for crypto every gap >1 bar). `Largest non-wknd` is `hours (after UTC-stamp, missing bars)`.


## EURUSDm

### Live symbol specs (`mt5.symbol_info`)

| field | value |
|---|---|
| digits | 5 |
| point | 1e-05 |
| trade_contract_size | 100000.0 |
| trade_tick_size | 1e-05 |
| trade_tick_value | 1.0 |
| trade_tick_value_profit | 1.0 |
| trade_tick_value_loss | 1.0 |
| volume_min | 0.01 |
| volume_step | 0.01 |
| volume_max | 200.0 |
| volume_limit | 0.0 |
| swap_long | -5.5 |
| swap_short | 0.0 |
| swap_mode | 1 (POINTS) |
| swap_rollover3days | 3 (Thu) |
| trade_stops_level | 0 |
| trade_freeze_level | 0 |
| trade_calc_mode | 0 (FOREX) |
| trade_mode | 4 |
| trade_exemode | 2 |
| margin_initial | 0.0 |
| margin_maintenance | 0.0 |
| margin_hedged | 0.0 |
| currency_base | EUR |
| currency_profit | USD |
| currency_margin | EUR |
| spread | 8 |
| spread_float | True |
| filling_mode | 3 |
| order_mode | 127 |
| expiration_mode | 15 |
| start_time | 0 |
| expiration_time | 0 |
| session_deals | 0 |
| path | Standard\Forex\EURUSDm |
| description | Euro vs US Dollar |
| trading sessions | not available: the `MetaTrader5` Python package has no `symbol_info_session_trade/quote`; see notes |

### Coverage

| TF | bars | first (UTC-stamp) | last | wknd gaps | non-wknd gaps | largest non-wknd | spread med / p90 (pts) | zero-spread % | zero-vol bars | cache action |
|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| D1 | 3940 | 2014-01-14 00:00:00 | 2026-10-16 00:00:00 | 661 | 9 | 72.0h (2015-12-24 00:00, 2) | 8 / 10 | 26.1 | 0 | replaced (old 2723 bars, backed up) |
| H4 | 16413 | 2014-01-14 00:00:00 | 2026-10-16 08:00:00 | 822 | 663 | 72.0h (2015-12-24 00:00, 17) | 8 / 10 | 7.6 | 0 | new |
| H1 | 60764 | 2014-01-14 00:00:00 | 2026-10-16 11:00:00 | 822 | 666 | 73.0h (2020-12-24 21:00, 72) | 9 / 10 | 3.4 | 0 | new |
| M15 | 100001 | 2022-10-11 17:30:00 | 2026-10-16 11:00:00 | 209 | 7 | 24.2h (2024-12-24 21:45, 96) | 8 / 10 | 0.0 | 0 | KEPT existing (old 100014 >= new 100001); fresh copy left in _staging |
| M5 | 100000 | 2025-06-13 19:30:00 | 2026-10-16 11:05:00 | 70 | 47 | 24.2h (2025-12-24 21:55, 289) | 8 / 9 | 0.0 | 0 | replaced (old 99613 bars, backed up) |
| M1 | 100000 | 2026-07-09 10:14:00 | 2026-10-16 11:09:00 | 14 | 1626 | 0.3h (2026-10-08 21:00, 17) | 8 / 8 | 0.0 | 0 | KEPT existing (old 100000 >= new 100000); fresh copy left in _staging |

## GBPUSDm

### Live symbol specs (`mt5.symbol_info`)

| field | value |
|---|---|
| digits | 5 |
| point | 1e-05 |
| trade_contract_size | 100000.0 |
| trade_tick_size | 1e-05 |
| trade_tick_value | 1.0 |
| trade_tick_value_profit | 1.0 |
| trade_tick_value_loss | 1.0 |
| volume_min | 0.01 |
| volume_step | 0.01 |
| volume_max | 200.0 |
| volume_limit | 0.0 |
| swap_long | -2.0 |
| swap_short | -0.7 |
| swap_mode | 1 (POINTS) |
| swap_rollover3days | 3 (Thu) |
| trade_stops_level | 0 |
| trade_freeze_level | 0 |
| trade_calc_mode | 0 (FOREX) |
| trade_mode | 4 |
| trade_exemode | 2 |
| margin_initial | 0.0 |
| margin_maintenance | 0.0 |
| margin_hedged | 0.0 |
| currency_base | GBP |
| currency_profit | USD |
| currency_margin | GBP |
| spread | 10 |
| spread_float | True |
| filling_mode | 3 |
| order_mode | 127 |
| expiration_mode | 15 |
| start_time | 0 |
| expiration_time | 0 |
| session_deals | 0 |
| path | Standard\Forex\GBPUSDm |
| description | Great Britain Pound vs US Dollar |
| trading sessions | not available: the `MetaTrader5` Python package has no `symbol_info_session_trade/quote`; see notes |

### Coverage

| TF | bars | first (UTC-stamp) | last | wknd gaps | non-wknd gaps | largest non-wknd | spread med / p90 (pts) | zero-spread % | zero-vol bars | cache action |
|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| D1 | 3940 | 2014-01-14 00:00:00 | 2026-10-16 00:00:00 | 661 | 9 | 72.0h (2015-12-24 00:00, 2) | 8 / 15 | 26.1 | 0 | replaced (old 2723 bars, backed up) |
| H4 | 16413 | 2014-01-14 00:00:00 | 2026-10-16 08:00:00 | 822 | 663 | 72.0h (2015-12-24 00:00, 17) | 9 / 15 | 7.6 | 0 | new |
| H1 | 60750 | 2014-01-14 00:00:00 | 2026-10-16 11:00:00 | 822 | 665 | 73.0h (2020-12-24 21:00, 72) | 10 / 15 | 3.4 | 0 | new |
| M15 | 100001 | 2022-10-11 16:45:00 | 2026-10-16 11:00:00 | 209 | 6 | 24.2h (2024-12-24 21:45, 96) | 10 / 12 | 0.0 | 0 | KEPT existing (old 100203 >= new 100001); fresh copy left in _staging |
| M5 | 100000 | 2025-06-13 13:45:00 | 2026-10-16 11:05:00 | 70 | 99 | 24.2h (2025-12-24 21:55, 289) | 10 / 11 | 0.0 | 0 | KEPT existing (old 100292 >= new 100000); fresh copy left in _staging |
| M1 | 100000 | 2026-07-10 00:36:00 | 2026-10-16 11:09:00 | 14 | 851 | 0.2h (2026-10-01 20:59, 12) | 10 / 10 | 0.0 | 0 | KEPT existing (old 100000 >= new 100000); fresh copy left in _staging |

## USDJPYm

### Live symbol specs (`mt5.symbol_info`)

| field | value |
|---|---|
| digits | 3 |
| point | 0.001 |
| trade_contract_size | 100000.0 |
| trade_tick_size | 0.001 |
| trade_tick_value | 0.6330075454499418 |
| trade_tick_value_profit | 0.6330075454499418 |
| trade_tick_value_loss | 0.6330476178418141 |
| volume_min | 0.01 |
| volume_step | 0.01 |
| volume_max | 300.0 |
| volume_limit | 0.0 |
| swap_long | 0.0 |
| swap_short | -13.9 |
| swap_mode | 1 (POINTS) |
| swap_rollover3days | 3 (Thu) |
| trade_stops_level | 0 |
| trade_freeze_level | 0 |
| trade_calc_mode | 0 (FOREX) |
| trade_mode | 4 |
| trade_exemode | 2 |
| margin_initial | 0.0 |
| margin_maintenance | 0.0 |
| margin_hedged | 0.0 |
| currency_base | USD |
| currency_profit | JPY |
| currency_margin | USD |
| spread | 10 |
| spread_float | True |
| filling_mode | 3 |
| order_mode | 127 |
| expiration_mode | 15 |
| start_time | 0 |
| expiration_time | 0 |
| session_deals | 0 |
| path | Standard\Forex\USDJPYm |
| description | US Dollar vs Japanese Yen |
| trading sessions | not available: the `MetaTrader5` Python package has no `symbol_info_session_trade/quote`; see notes |

### Coverage

| TF | bars | first (UTC-stamp) | last | wknd gaps | non-wknd gaps | largest non-wknd | spread med / p90 (pts) | zero-spread % | zero-vol bars | cache action |
|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| D1 | 1555 | 2021-10-27 00:00:00 | 2026-10-16 00:00:00 | 259 | 0 | none | 10 / 11 | 0.1 | 0 | replaced (old 1537 bars, backed up) |
| H4 | 8003 | 2021-10-27 16:00:00 | 2026-10-16 08:00:00 | 259 | 5 | 24.0h (2024-12-24 20:00, 5) | 10 / 11 | 0.0 | 0 | new |
| H1 | 30959 | 2021-10-27 17:00:00 | 2026-10-16 11:00:00 | 259 | 6 | 25.0h (2024-12-24 21:00, 24) | 10 / 11 | 0.0 | 0 | new |
| M15 | 100001 | 2022-10-11 16:30:00 | 2026-10-16 11:00:00 | 209 | 7 | 24.2h (2024-12-24 21:45, 96) | 10 / 11 | 0.0 | 0 | KEPT existing (old 101163 >= new 100001); fresh copy left in _staging |
| M5 | 100000 | 2025-06-13 13:25:00 | 2026-10-16 11:05:00 | 70 | 99 | 24.2h (2025-12-31 21:55, 290) | 10 / 10 | 0.0 | 0 | KEPT existing (old 100871 >= new 100000); fresh copy left in _staging |
| M1 | 100000 | 2026-07-09 23:14:00 | 2026-10-16 11:09:00 | 14 | 908 | 0.3h (2026-10-08 20:59, 18) | 10 / 10 | 0.0 | 0 | replaced (old 98082 bars, backed up) |

## BTCUSDm

### Live symbol specs (`mt5.symbol_info`)

| field | value |
|---|---|
| digits | 2 |
| point | 0.01 |
| trade_contract_size | 1.0 |
| trade_tick_size | 0.01 |
| trade_tick_value | 0.01 |
| trade_tick_value_profit | 0.01 |
| trade_tick_value_loss | 0.01 |
| volume_min | 0.01 |
| volume_step | 0.01 |
| volume_max | 200.0 |
| volume_limit | 0.0 |
| swap_long | -1910.2 |
| swap_short | 0.0 |
| swap_mode | 1 (POINTS) |
| swap_rollover3days | 5 (Sat) |
| trade_stops_level | 0 |
| trade_freeze_level | 0 |
| trade_calc_mode | 0 (FOREX) |
| trade_mode | 4 |
| trade_exemode | 2 |
| margin_initial | 0.0 |
| margin_maintenance | 0.0 |
| margin_hedged | 0.0 |
| currency_base | BTC |
| currency_profit | USD |
| currency_margin | BTC |
| spread | 640 |
| spread_float | True |
| filling_mode | 3 |
| order_mode | 127 |
| expiration_mode | 15 |
| start_time | 0 |
| expiration_time | 0 |
| session_deals | 0 |
| path | Standard\Crypto\BTCUSDm |
| description | Bitcoin vs US Dollar |
| trading sessions | not available: the `MetaTrader5` Python package has no `symbol_info_session_trade/quote`; see notes |

### Coverage

| TF | bars | first (UTC-stamp) | last | wknd gaps | non-wknd gaps | largest non-wknd | spread med / p90 (pts) | zero-spread % | zero-vol bars | cache action |
|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| D1 | 1816 | 2021-10-27 00:00:00 | 2026-10-16 00:00:00 | 0 | 0 | none | 1780 / 2896 | 0.0 | 0 | new |
| H4 | 10886 | 2021-10-27 16:00:00 | 2026-10-16 08:00:00 | 0 | 1 | 16.0h (2021-10-27 16:00, 3) | 1800 / 3240 | 0.0 | 0 | new |
| H1 | 43536 | 2021-10-27 17:00:00 | 2026-10-16 11:00:00 | 0 | 5 | 16.0h (2021-10-27 17:00, 15) | 1800 / 3523 | 0.0 | 0 | new |
| M15 | 100000 | 2023-12-09 17:00:00 | 2026-10-16 11:00:00 | 0 | 5 | 1.2h (2024-01-13 04:45, 4) | 2160 / 3397 | 0.0 | 0 | new |
| M5 | 100000 | 2025-11-03 03:55:00 | 2026-10-16 11:05:00 | 0 | 12 | 0.5h (2025-12-06 06:05, 5) | 1400 / 1800 | 0.0 | 0 | new |
| M1 | 100000 | 2026-08-07 23:39:00 | 2026-10-16 11:09:00 | 0 | 9 | 0.2h (2026-09-12 06:49, 12) | 1000 / 1000 | 0.0 | 0 | new |

## ETHUSDm

### Live symbol specs (`mt5.symbol_info`)

| field | value |
|---|---|
| digits | 2 |
| point | 0.01 |
| trade_contract_size | 1.0 |
| trade_tick_size | 0.01 |
| trade_tick_value | 0.01 |
| trade_tick_value_profit | 0.01 |
| trade_tick_value_loss | 0.01 |
| volume_min | 0.1 |
| volume_step | 0.01 |
| volume_max | 2000.0 |
| volume_limit | 0.0 |
| swap_long | -57.1 |
| swap_short | 0.0 |
| swap_mode | 1 (POINTS) |
| swap_rollover3days | 5 (Sat) |
| trade_stops_level | 0 |
| trade_freeze_level | 0 |
| trade_calc_mode | 0 (FOREX) |
| trade_mode | 4 |
| trade_exemode | 2 |
| margin_initial | 0.0 |
| margin_maintenance | 0.0 |
| margin_hedged | 0.0 |
| currency_base | ETH |
| currency_profit | USD |
| currency_margin | ETH |
| spread | 100 |
| spread_float | True |
| filling_mode | 3 |
| order_mode | 127 |
| expiration_mode | 15 |
| start_time | 0 |
| expiration_time | 0 |
| session_deals | 0 |
| path | Standard\Crypto\ETHUSDm |
| description | Ethereum vs US Dollar |
| trading sessions | not available: the `MetaTrader5` Python package has no `symbol_info_session_trade/quote`; see notes |

### Coverage

| TF | bars | first (UTC-stamp) | last | wknd gaps | non-wknd gaps | largest non-wknd | spread med / p90 (pts) | zero-spread % | zero-vol bars | cache action |
|---|---:|---|---|---:|---:|---|---|---:|---:|---|
| D1 | 1816 | 2021-10-27 00:00:00 | 2026-10-16 00:00:00 | 0 | 0 | none | 170 / 372 | 0.0 | 0 | new |
| H4 | 10886 | 2021-10-27 16:00:00 | 2026-10-16 08:00:00 | 0 | 1 | 16.0h (2021-10-27 16:00, 3) | 180 / 410 | 0.0 | 0 | new |
| H1 | 43536 | 2021-10-27 17:00:00 | 2026-10-16 11:00:00 | 0 | 5 | 16.0h (2021-10-27 17:00, 15) | 180 / 430 | 0.0 | 0 | new |
| M15 | 100000 | 2023-12-09 17:00:00 | 2026-10-16 11:00:00 | 0 | 5 | 1.2h (2024-01-13 04:45, 4) | 180 / 485 | 0.0 | 0 | new |
| M5 | 100000 | 2025-11-03 04:05:00 | 2026-10-16 11:10:00 | 0 | 12 | 0.5h (2025-12-06 06:05, 5) | 140 / 140 | 0.0 | 0 | new |
| M1 | 100000 | 2026-08-07 18:03:00 | 2026-10-16 11:14:00 | 0 | 292 | 0.2h (2026-09-12 06:49, 12) | 100 / 100 | 0.0 | 0 | new |

## Problems and caveats (read before building cost models)

1. **Terminal bar cap.** `terminal_info().maxbars = 100000`. Every M15/M5/M1 series is capped at about 100k bars (that is the "as far back as the broker provides" ceiling for these TFs on this terminal, not the broker's real depth). Resulting intraday depth: FX M15 about 4.0y (from 2022-10), FX M5 about 1.3y (from 2025-06), M1 about 3.3 months (from 2026-07); crypto M15 about 2.85y, M5 about 11.5 months, M1 about 10 weeks. D1/H4/H1 are below the cap and are the full broker history (FX D1/H4/H1 from 2014-01-14, USDJPY/BTC/ETH D1/H4/H1 from 2021-10-27). Raising "Max bars in chart" in the terminal and restarting it would deepen M15/M5/M1; not done (settings are out of scope).
2. **EURUSDm / GBPUSDm H1 and H4 are sparse before 2017-03.** From 2014-01-14 to 2017-02-28 there is exactly **1 bar per day** (the 00:00 bar), about 300 bars a year, i.e. daily data labelled as H1/H4; the manifest shows about 650 gaps of exactly 24h for this. Intraday-usable FX H1/H4 starts **2017-03-01** (about 19-20 H1 bars/day). This is why the "non-weekend gaps" count is about 660 for FX H1/H4. USDJPYm/BTC/ETH do not have this issue.
3. **Cache action mix (strictly-longer rule).** Where a file already existed (Sep 27 download, stale: ends 2026-09-24/25) the new download replaced it only if it had strictly more bars. Because of the 100k cap this is decided by a few hundred bars, not by freshness:
   - replaced (old copies in `research/data/_backup/*.bak`): EURUSDm D1, GBPUSDm D1, USDJPYm D1, EURUSDm M5, USDJPYm M1.
   - **kept stale** (existing file has >= bars; fresh download ending 2026-10-16 is in `research/data/_staging/<name>.npy` + `.manifest.json`, hash-valid): EURUSDm M15, M1; GBPUSDm M15, M5, M1; USDJPYm M15, M5. The kept files end 2026-09-24/25 (3 weeks stale) but reach back 1-4 months further. Decide per use whether to swap in the staged copies. Note EURUSDm M5 was replaced by a fresher file that starts 2025-06-13 instead of 2025-05-26 (loses 3 weeks at the front, gains 3 weeks at the end).
   - XAUUSDm_* files untouched (mtimes unchanged).
4. **Crypto trades 7 days.** BTCUSDm/ETHUSDm have Saturday/Sunday bars (about 28.6% of bars) and zero weekend gaps; the pipeline's weekend flag is FX-oriented, so crypto "non-weekend gaps" are just short feed holes (M1: 9 for BTC, 292 for ETH, mostly 1-2 missing minutes; the worst is 16h at the very start of H1/H4, 2021-10-27, i.e. the first bars). Any session/weekend filter built for gold/FX must be disabled for crypto. D1 bars are anchored 00:00 broker time.
5. **Spreads are bar-recorded and regime dependent.** Spread median differs sharply across TFs for crypto because each TF covers a different era (BTC median 1780 pts D1 / 2160 M15 / 1400 M5 / 1000 M1 where 1 pt = 0.01 USD, i.e. about 10-22 USD; ETH 170 / 180 / 140 / 100 pts = about 1.0-1.8 USD). Use the M1/M5 (recent) numbers for current cost; the long-history numbers for stress. FX D1/H4/H1 spread values include 26.1% / 7.6% / 3.4% zero-spread bars (EURUSD/GBPUSD D1/H4/H1; likely concentrated in the old era), so FX long-history spread stats are biased low; recent M15-M1 FX spread is 8-10 pts (EURUSD, GBPUSD), 10 pts (USDJPY).
6. **Trading sessions not retrievable.** The `MetaTrader5` Python package exposes no `symbol_info_session_trade` / `symbol_info_session_quote` (AttributeError), so session times are absent; the next stage should infer them from the bars themselves (hour-of-week bar occupancy); crypto is effectively continuous.
7. **Symbol-spec oddities for cost models.** `trade_calc_mode` is 0 (FOREX) and `margin_initial/maintenance` are 0 for all five including crypto, so margin comes from account leverage, not from the symbol record (would need `order_calc_margin`, not called). `swap_mode` = 1 (POINTS) for all: swap values are in points per lot per day (BTC long -1910.2 pts = about -19.10 USD per 1.0 lot, ETH long -57.1 pts = -0.571 USD per 1.0 lot), triple swap on Thursday (FX) / Saturday (crypto). `ETHUSDm.volume_min` is 0.1 (not 0.01). USDJPY `trade_tick_value` is about 0.633 USD (JPY converted at the current rate, it drifts). Crypto contract size is 1 coin; FX 100000 units (the "m" symbols here report FX lot size 100000 with min lot 0.01).
8. **Tooling note.** MT5 `initialize()` and first access to a symbol occasionally stalled for 5-30 s (terminal busy); one fetch process had to be restarted for ETHUSDm. No data was lost.
9. **Verification.** `load_bars(sym, ("M15","M5","M1","D1","H4","H1"))` passes the sha256 check for all 5 symbols and all 6 timeframes (30 files). Only read-only MT5 calls were used (`initialize`, `account_info`, `terminal_info`, `symbol_select`, `symbol_info`, `copy_rates_from_pos` for probing, `copy_rates_range`, `shutdown`).

