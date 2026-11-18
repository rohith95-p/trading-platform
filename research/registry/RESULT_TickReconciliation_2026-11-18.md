# Tick execution reconciliation — historical source blocked; offline tool verified

Protocol `PREREG_TickReconciliation_2026-11-18.md` was committed in `69fc353`
before either request, implementation, fixture replay or tests. **No historical
tick execution reconciliation was completed.** No orders, holdout observations,
account sign-in, terminal auto-launch or paid service were used.

## Actual acquisition findings

Frozen requested hour: 2025-01-06 12:00–13:00 UTC.

1. Official raw archive URL
   `https://datafeed.dukascopy.com/datafeed/XAUUSD/2025/00/06/12h_ticks.bi5`
   failed with Windows connection-reset error 10054. No retry was made.
2. A single request to the alternate official-domain API
   `https://jetta.dukascopy.com/v1/ticks/XAU-USD/2025/1/6/12` returned HTTP 202,
   `x-amzn-waf-action: challenge`, with an empty response. This is **not an empty
   historical trading hour** and was not parsed as data. No challenge bypass or
   repeated request was attempted.
3. The provider's current historical export documentation describes credentialed
   Requester-Pays storage; that route was not used. See
   [Dukascopy historical export](https://wiki.dukascopy.com/en/development/data-export/).
4. Local read-only file inventory found one proprietary native cache:
   `Exness-MT5Trial11/ticks/XAUUSDm/202610.tkc`, 1,452,957 bytes, modified
   2026-10-19 15:06:36 UTC. No `terminal64` process was running. A directory name
   is not verified demo identity. This binary was not decoded or called
   historical tick evidence, and the terminal was not launched.ip

Raw acquisition logs and source URLs are preserved under
`research/data/tick_reconciliation_2026-11-18/`. The attempted dates were never
changed in response to trading outcomes.

## Read-only intended-demo capture tool

`scripts/validation/mt5_demo_tick_capture.py`:

- Requires an already-running terminal matching an explicit executable path.
  It refuses to auto-launch a terminal.
- Requires exact expected login and server, and checks the terminal's actual
  `ACCOUNT_TRADE_MODE_DEMO` flag before and after retrieving history. Real and
  contest accounts and mid-capture identity changes fail closed.
- Restricts symbols to XAUUSD/XAUUSDm, windows to at most 24 hours, and timestamps
  to strictly before the 2026-11-01 holdout boundary.
- Reads account identity, contract metadata and historical bid/ask quotes only.
  It contains no login, order submission or terminal-settings mutation.
- Requires UTC-aware timestamps, checks nondecreasing millisecond quote order,
  positive uncrossed finite bid/ask, and records duplicate-time observations.
  Only an exactly inclusive terminal end boundary is clipped; unexpected
  out-of-range quotes fail rather than silently deleting a time-domain error.
- Saves `.npy` quotes and hashed manifest to new paths. Account login is hashed
  with server in the manifest rather than printed. Current contract metadata is
  explicitly distinguished from historical fee terms.

Prepared command, with the actual manually verified demo details supplied:

```powershell
.\venv\Scripts\python.exe scripts/validation/mt5_demo_tick_capture.py --terminal-path "C:\path\to\terminal64.exe" --expected-login DEMO_LOGIN --expected-server "EXACT_DEMO_SERVER" --start 2025-01-06T12:00:00Z --end 2025-01-06T13:00:00Z --out research/data/demo_ticks_2025-01-06.npy
```

The official API specifies UTC-aware `copy_ticks_range` requests and distinguishes
demo account mode. [Tick history API](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py),
[account mode constants](https://www.mql5.com/en/docs/constants/environment_state/accountinformation).
These docs support the API contract; they do not prove this intended broker's
history completeness, exact timestamp convention or execution quality.

## Executed synthetic engineering comparison

Because historical tick acquisition was blocked, the executed data are explicitly
**66 programmed toy quotes, not historical gold prices**. Two fixed order
fixtures were replayed separately through an independent ordered-quote simulator
and the actual `BacktestEngine`, using matched tick-derived M1 bid OHLC and the
opening spread. The fixture engine uses deterministic fixed stop geometry and no
predictive strategy. These synthetic execution inputs are not spliced into the
master dataset or presented as a candidate backtest.

Assumptions match the protocol: 0.02 lots, 100 oz/lot, $1/oz stop, $1.50/oz
target, $0.02/oz adverse market/stop slippage, $3.50/lot round-trip commission.

| Fixture | Ordered quotes | M1 approximation | Tick net / M1 net | Observed quote DD / sampled M1 DD |
|---|---|---|---:|---:|
| BUY: target quote occurs before later stop quote within same minute | TP | SL under stop-first ambiguity | +$2.93 / −$2.11 | $0.51 / $2.11 |
| SELL: ask-only spread spike hits stop before later price decline | SL at actual ask plus slip | TP; fixed opening spread misses ask spike | −$3.15 / +$2.93 | $3.15 / $0.51 |

Both paths entered once per fixture with identical entry prices. The bar exit
timestamp label precedes the actual trigger quote by 200 ms in these examples;
its OHLC does not encode that trigger time. These deliberately constructed
cases demonstrate the missing information in minute bars; their frequencies
or P&Ls say nothing about real gold market profitability.

Saved `research/results/tick_reconciliation_2026-11-18/comparison.json` contains
full configurations, trade records, price/time/P&L discrepancies and drawdowns;
`input_quotes.npy` freezes the toy input. `provenance.json` records code hashes,
failed source attempts and local-cache findings. `historical_verification=false`
is explicit, including when a saved file is provided without certified provenance.

## Validation

```
.\venv\Scripts\python.exe -m pytest tests/test_tick_execution_fixture.py -q
.\venv\Scripts\python.exe scripts/validation/tick_fixture_reconciliation.py
```

**14 focused tests passed.** They verify the known quote-order/ask-spike
discrepancies, duplicate-time source order, rejection of bad/empty quotes, demo
identity pinning, rejection of real/contest accounts, account-switch detection,
UTC/holdout bounds, read-only API calls and refusal to auto-launch a terminal.
Tests use an offline mock terminal, not an actual broker demo. The default fixture
runner refuses to overwrite its frozen result directory.

## Remaining blocker

Historical tick verification needs an accessible free source or an explicitly
identified running demo terminal supplying the requested history. Broker-specific
execution verification additionally needs intended-demo order/deal records and
native tester reconciliation. The prepared read-only capture alone does not
verify fills, slippage, queue position or live strategy parity. **No strategy or
account readiness classification is improved by the synthetic fixture.**
