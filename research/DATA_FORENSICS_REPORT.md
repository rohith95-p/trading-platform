# Data forensics report — 2026-11-18

Scanned 36 accessible NPY/CSV files under research/data* and research/events. Per-file content hashes and numerical diagnostics are saved in market_atlas.json. This is a bounded inventory, not a claim to have inspected all laptop files or JSON trade records.

| File | Rows | Preholdout rows | Duplicates | Largest elapsed gap seconds | Error |
|---|---:|---:|---:|---:|---|
| research/data/bls_windows/f62546278584c219520d700632d932bb22917cec8c910b7329092fd764d6a32e.npy | 9943 | 9943 | 0 | 0 |  |
| research/data/d1_study/dxy.csv | 14135 | 14135 | 0 | 604 |  |
| research/data/d1_study/gld.csv | 5481 | 5481 | 0 | 432 |  |
| research/data/d1_study/gold.csv | 6527 | 6527 | 0 | 432 |  |
| research/data/d1_study/master.csv | 6527 | 6527 | 0 | 432 |  |
| research/data/d1_study/spx.csv | 24784 | 24784 | 0 | 1037 |  |
| research/data/d1_study/vix.csv | 9235 | 9235 | 0 | 604 |  |
| research/data/d1_study/y10.csv | 16154 | 16154 | 0 | 604 |  |
| research/data/dukascopy_2025/XAUUSD_M1_bidask.npy | 369312 | 369312 | 0 | 0 |  |
| research/data/genesis/2013_M1.npy | 353345 | 353345 | 0 | 0 |  |
| research/data/genesis/2013_M5.npy | 70405 | 70405 | 0 | 0 |  |
| research/data/genesis/2018_M1.npy | 354711 | 354711 | 0 | 0 |  |
| research/data/genesis/2018_M5.npy | 70912 | 70912 | 0 | 0 |  |
| research/data/genesis/2025_M1.npy | 327369 | 327369 | 0 | 0 |  |
| research/data/genesis/2025_M5.npy | 65351 | 65351 | 0 | 0 |  |
| research/data/gvz_through_2025.csv | 4095 | 4095 | ? | ? |  |
| research/data/kaggle_22yr/XAUUSDm_D1.npy | 5558 | 5558 | 0 | 0 |  |
| research/data/kaggle_22yr/XAUUSDm_M1.npy | 6822714 | 6822714 | 0 | 0 |  |
| research/data/kaggle_22yr/XAUUSDm_M15.npy | 496556 | 496556 | 0 | 0 |  |
| research/data/kaggle_22yr/XAUUSDm_M5.npy | 1450368 | 1450368 | 0 | 0 |  |
| research/data/miners_factor_closes_through_2025.csv | 4935 | 4935 | ? | ? |  |
| research/data/selection_inputs/7132368ef74b14883d2a84045c37f158db70a97e38d7a728486845d942baa3cf.csv | 1043 | 1043 | ? | ? |  |
| research/data/XAUUSDm_D1.npy | 1544 | 1544 | 0 | 0 |  |
| research/data/XAUUSDm_H1.npy | 28599 | 28599 | 0 | 0 |  |
| research/data/XAUUSDm_H4.npy | 7498 | 7498 | 0 | 0 |  |
| research/data/XAUUSDm_M1.npy | 100000 | 100000 | 0 | 0 |  |
| research/data/XAUUSDm_M15.npy | 100000 | 100000 | 0 | 0 |  |
| research/data/XAUUSDm_M5.npy | 100000 | 100000 | 0 | 0 |  |
| research/data_2026-10-30/XAUUSDm_D1.npy | 1558 | 1558 | 0 | 0 |  |
| research/data_2026-10-30/XAUUSDm_M1.npy | 100000 | 100000 | 0 | 0 |  |
| research/data_2026-10-30/XAUUSDm_M15.npy | 100000 | 100000 | 0 | 0 |  |
| research/data_live_parity/XAUUSDm_D1.npy | 197 | 197 | 0 | 0 |  |
| research/data_live_parity/XAUUSDm_M1.npy | 27556 | 27556 | 0 | 0 |  |
| research/data_live_parity/XAUUSDm_M15.npy | 5038 | 5038 | 0 | 0 |  |
| research/data_live_parity/XAUUSDm_M5.npy | 9329 | 9329 | 0 | 0 |  |
| research/events/usd_high_impact_2022_2026.csv | 220 | 220 | 0 | 2420 |  |

## Interpretation and restrictions

Elapsed gaps include scheduled closures; no complete historical broker session/holiday calendar has been established. Duplicate event timestamps can be legitimate simultaneous releases; they are not automatically duplicate events. Missing fields are not imputed. NPY rows after November1 are counted by timestamp but their prices are excluded from diagnostics. Whole-file hashing does not evaluate holdout returns.

Broker/archive source priority and the January2026 archive cutoff remain as declared in master.py. Dukascopy bid/ask snapshots remain separate and are not spliced into broker data. A valid OHLC envelope is not verification of first-touch ordering or a complete tick history. Spread points require historical point/digit metadata; zero values are not free execution. Tick volume is quote activity rather than centralized gold transaction volume.

The September–October2025 archive hole and January2026 archive divergence invalidate continuous account conclusions through those spans without a declared missing-data policy. Historical backtest artifacts with unchecked gaps are not upgraded by this inventory. A recent broker cache does not reconstruct prior actual Atlas terms or fills.

Raw daily macro CSVs lack vintage and close-time availability. Event-calendar source labels/verified flags are metadata, not independent release-time or surprise validation. Remaining trade-log forensics and native-tick/broker reconciliation are documented separately in BACKTEST_REALITY_AUDIT and DEPLOYMENT_READINESS.

The daily gold proxy contains441 inconsistent OHLC envelopes; for example2001-02-13 has open/high/low261 and close260.299988, and2003-04-29 has open/high/low333 and close333.700012. Settlement or adjustment conventions require source verification. Do not use these rows as executable gold OHLC. The BLS array is163×61 event windows; its flattened representation is annotated and is not certified as a continuous tradable series. Archive and Genesis spread columns are100% zero, hence missing cost evidence rather than zero-cost execution.

Master M5 includes100,000 observations although a larger raw M5 archive exists: master source declarations do not select that archive resolution. This source-coverage difference, and limited native H4 history, confound cross-timeframe rankings. The audit preserved the loader declarations.
