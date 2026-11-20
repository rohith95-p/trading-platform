# Forecast-to-Fill: reproducibility audit and fixed XAUUSD core

Source https://arxiv.org/html/2511.08571v1 . Audit before this runner:
lambda and the training search values are not supplied; de-risking allows halving or
closing; body T+0 baseline differs from clarification T+1 baseline. Six-month slices
advanced monthly overlap; reconstruction needs actual assignment/ledger, not just a block
bootstrap. The source notes price coverage to16Sep2025 but extends calendar to31Oct by
forward filling: those extra rows supply no new observed market return. No linked
author code/trade ledger was found in the paper or targeted public search on2026-11-11.
These are reproducibility limitations, not proof of misconduct or that the idea cannot work.

Independent core adaptation, no claimed paper replication. All orders XAUUSD, .02 fixed
lots, NY17:00 FX session boundary (New York wall clock+7h server day). Use fully closed
session OHLC from M15, no fictional flat market days. EMA log-price lambda=.9, fixed
researcher assumption (source leaves lambda calibrated but unspecified). Momentum50days,
weight .6 slope-confidence +.4 positive-momentum indicator, slope z clipped[-3,3] and
mapped to[0,1]. Long eligibility p>=.52 and positive smoothed log slope; exit on p<.5.

On Jan1/Jul1 each year from2015, freeze slope mean/sample-SD from preceding10 calendar
years, require>=2000 completed sessions. No overlapping OOS assignments or tuning. ATR14
simple mean. Signal on session t close fills at session t+2 open (one whole intervening
completed session), an executable approximation to source T+1 close. At entry use signal
ATR: stop2ATR. Closed-day highest bid updates trailing stop to peak-1.5 latest dailyATR,
but changed stops first active at next session open; never trail using current day's future
high before testing earlier minutes. ATR stop distance may contract/expand; trail ratchets
up only. Max age30 sessions, close on delayed decision queue at next executable open.
One position, no pyramiding. Time exits counted in trading sessions, not calendar days.
Final window liquidation explicit. Stop gaps at worse opening bid, market/stop slippage
$.02 each; observed/fallback ask spread, .07 roundtrip commission, long swap per ECN model.

Fixed size isolates core signal; no unprovided Kelly training objective/search, vol sizing,
capacity scaling, futures rolls or paper gamma impact assumed. Broker historical financing
is approximate current swap rather than point-in-time series. Signal data session close
differs from futures settlement. This is multiday, not everyday roundtrip trading.
Evaluate2015–18,2019–21,2022–25; previously inspected historical prices. PF>=1.3 and
positive net every era required to advance. Store exact train cutoffs, per-trade dates,
metrics/ablation/MC; independently test future-prefix invariance. November2026 untouched.
