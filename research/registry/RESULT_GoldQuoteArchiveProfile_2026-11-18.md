# Gold quote activity by session, January–October 2026

The Standard-account archive yielded 80,478,503 bid/ask updates and 294,988 observed UTC minutes. All ten monthly files parsed. The price, symbol and timestamp checks excluded zero quotes. There were 639,063 consecutive updates at an identical millisecond and zero backward timestamps. Source order was retained for ties.

| Local clock group | Observed minutes | Median quote updates/min | Median of minute mean spreads, USD/oz | Median intraminute bid range, USD/oz |
|---|---:|---:|---:|---:|
| London only | 63,300 | 165 | 0.260 | 1.857 |
| New York only | 61,800 | 156 | 0.260 | 1.712 |
| London–New York overlap | 52,800 | 337 | 0.260 | 3.010 |
| Outside both | 117,088 | 169 | 0.260 | 1.959 |

During the overlap, this feed typically updated more than twice as often as it did in London-only minutes. The median spread was very similar across groups while the median bid range was larger in the overlap. Equal medians can conceal extreme spreads. The observation count weights active minutes equally and omits minutes without quotes. The clock groups describe 08:00–17:00 weekdays in each city's own time zone. They can include local holidays.

The original monthly files contain successive broker quotes. The derived files preserve bid and ask OHLC, spread statistics and the count for every observed minute. They provide a separately sourced history for months in which the old backtester had missing M1 data. Prior backtest results retain their original inputs. [Preregistered method](PREREG_GoldQuoteArchiveProfile_2026-11-18.md) · [Monthly files, hashes and measurements](../xauusd_archive/quote_profile.json)

An independent CSV reader matched quote count, bid and ask OHLC, and mean spread for the second observed minute of each month. Each derived month's total row count and source hash matched its original archive record. [Verification checks](../xauusd_archive/verification.json)
