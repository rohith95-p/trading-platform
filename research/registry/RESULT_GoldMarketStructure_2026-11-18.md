# Dependence and historical shifts in gold

The signed partial autocorrelation of adjacent M1 and M15 returns was −0.0224 and −0.0176 respectively. Conditioning on intervening returns left little linear dependence at lags two through four in those samples. Discretized absolute-return dependence exceeded signed-return dependence at five of six resolutions. D1 had a small sample of uninterrupted runs, especially at long lags. These descriptive relationships use reference closes.

| Timeframe | Signed partial correlations, lags 1 through 4 | Mutual information, signed / absolute, bits | Strongest eligible shift | Adjusted p |
| --- | --- | --- | --- | ---: |
| M1 | −0.0224, −0.0034, −0.0026, −0.0026 | 0.0321 / 0.0574 | July 2009 | 0.006 |
| M5 | +0.0064, −0.0035, +0.0039, −0.0072 | 0.0165 / 0.0357 | Insufficient complete years | — |
| M15 | −0.0176, +0.0025, −0.0034, +0.0020 | 0.0244 / 0.0455 | February 2012 | 0.084 |
| H1 | −0.0020, −0.0011, −0.0009, +0.0012 | 0.0175 / 0.0344 | February 2012 | 0.102 |
| H4 | +0.0193, −0.0219, +0.0320, −0.0153 | 0.0102 / 0.0184 | Insufficient complete years | — |
| D1 | −0.0123, −0.0432, −0.0565, insufficient lag-four windows | 0.0081 / 0.0069 | January 2014 | 0.294 |

Only M1 met the prespecified adjusted 5% threshold for a single historical change in typical movement size. Its mean monthly median absolute 1-minute return was 2.27 basis points before July 2009 and 1.08 afterward across the eligible complete years. The change is retrospective. Variation in feed construction or coverage can also generate a break. These figures do not identify its cause, imply an actionable change date or measure trading profits.

Run `python -m scripts.research.gold_market_structure` after exporting the master files. All four partial correlation calculations were independently compared with explicit endpoint residual regressions on a synthetic gapped series. [Registered method](PREREG_GoldMarketStructure_2026-11-18.md) · [Counts, contingency tables, fitted boundaries and data hashes](../xauusd_archive/market_structure.json)
