# Forecasting the size and direction of the next gold move

The prior hour's four absolute M15 returns improved forecasts of the magnitude of the next return across all three periods. The model for signed returns failed the registered criterion. Both used coefficients fitted once on 303,023 windows from 2004–2018. The comparator always predicts the corresponding training mean.

| Evaluation dates | Windows | Absolute-return MSE reduction | Signed-return MSE reduction | Direction hit rate | Always-up hit rate | Signed reference move, USD/oz before costs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2019–2024 | 133,825 | 15.53% | 0.027% | 51.04% | 50.33% | +0.0186 |
| 2025 | 22,348 | 12.38% | −0.016% | 50.76% | 51.57% | −0.0076 |
| 2026 through October 29 | 18,544 | 23.58% | −0.066% | 51.17% | 50.50% | +0.0273 |

The 95% month-bootstrap intervals for the mean reduction in squared magnitude error were [6.77, 12.33], [3.93, 18.24] and [22.74, 100.67] squared basis points. All three intervals for the improvement in signed forecasts included zero. The fitted fourth-lag coefficients were +0.1156 for absolute returns and +0.00468 for signed returns, conditional on the other lags. The later periods were outside model fitting but had featured in previous project research.

The fixed historical mean is a weak comparator when volatility changes over years or systematically across a session. A risk application needs comparison against adaptive and time-of-day baselines and evidence that conditioning on the forecast improves realized risk. These observations cover contiguous M15 windows only. The data omit reopening gaps and the reference move excludes spread, fees and slippage. This study estimates forecast accuracy and cannot establish win rate on executed trades or an Atlas payout probability.

Reproduce with `python -m scripts.research.gold_m15_forecast`. Standalone synthetic checks verified end timestamps, return alignment, gap and nonfinite-window exclusion, and constant-gain bootstrap behavior. [Protocol](PREREG_GoldM15Forecast_2026-11-18.md) · [Machine-readable results](../results/gold_m15_forecast_2026-11-18.json)
