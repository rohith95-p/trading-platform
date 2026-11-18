# Sampled floating equity engineering verification

Protocol: `PREREG_SampledEquity_2026-11-18.md`, committed in `893c8bb` before
implementation, tests and the cached replay. No strategy changes or November
holdout access. This is an engineering benchmark, **not strategy qualification**.

## Implemented evidence

`BacktestResult.equity` remains closed balance. With
`EngineConfig(record_equity_samples=True)`, `equity_samples` separately records
opening quotes, post-order opening state, interval ends and final settlement.
Each record includes bid, reconstructed ask, balance, per-position mark/size/entry,
floating P&L, modeled accrued financing and reserved full round-trip commission.

- Gross equity = closed cash balance + marked floating P&L.
- Net liquidation equity = gross equity + accrued swap − pending commission.
- Drawdown tracks sampled peaks for both curves, seeded by initial capital.
- Sampling is observational; tests confirm identical trades and balance curves
  with it enabled versus disabled.
- Detailed sampling is opt-in to avoid multi-decade memory expansion.
- Full continuous/broker drawdown remains explicitly unverified.

## Fixed real-cache benchmark

UTC window: **2026-09-01 inclusive to 2026-09-15 exclusive**. Frozen existing
four-strategy `PORTFOLIO`; $5,000 initial capital; 0.02 lots; three-position caps;
7,500-bar history; causal M1 order; opening-price proxy; existing ECN costs;
protector/trailing/pyramiding off. Other configuration is stored verbatim.
The window was previously explored and provides no independent alpha test.

| Measurement | Result |
|---|---:|
| Completed trades | 5 |
| Net realized P&L | +$0.858 |
| Profit factor | 1.007196 |
| Closed-balance maximum drawdown | $90.306 |
| Sampled gross-equity maximum drawdown | $119.50 / 2.364746% |
| Sampled net-liquidation maximum drawdown | $119.50 / 2.364779% |
| Equity sample records | 40,366 |
| Independent sample reconciliation errors | 0 |
| Independent trade arithmetic errors | 0 |
| Partial M15 candles skipped | 13 |
| Missing M1 observations in those candles | 27 |
| Open-position exits unchecked in skipped candles | 0 |

The larger sampled drawdown demonstrates why a balance-only report understates
this benchmark's observed mark-to-market loss. It does not establish the worst
intraminute drawdown or actual broker risk.

## Reproduction and files

```
.\venv\Scripts\python.exe scripts/validation/sampled_equity_benchmark.py
.\venv\Scripts\python.exe -m pytest tests/test_sampled_equity.py tests/test_execution_reality.py tests/test_engine_live_parity.py tests/test_bias_audit_knobs.py tests/test_execution_audit_helpers.py tests/test_execution_delay.py -q
```

The runner refuses to overwrite its frozen result directory. Preserve the first
record if repeating the study in another directory/check-out. **87 focused tests
passed**. No new candidate or optimization trial was run.

Saved evidence:

- `research/results/sampled_equity_2026-11-18/benchmark.json`: all five trades,
  complete configuration/cost/spec metadata, diagnostics, source-code SHA-256s,
  master-input identity `8a50443c394719a6`, independent reconciliation and summary.
- `research/results/sampled_equity_2026-11-18/samples.json.gz`: every sampled state;
  compressed file hash recorded in `benchmark.json`.
- `scripts/validation/sampled_equity_check.py`: separate arithmetic using input
  M1 quotes, trade identities, configured fees and independently accumulated
  cash/drawdown. It does not import the engine's sampler.

## Limits

Only opening and closing quotes are sampled. Intraminute extremes and quote
ordering are unknown; missing candles may censor possible entries. Ask extrema
are not observed. Financing/commission reserves follow scenario assumptions,
not a broker statement. End-of-data trade timestamp retains its existing
minute-open label while the sampled quote is the interval close; rollover at
that terminal boundary needs finer reconciliation in future studies. No trade
in this particular benchmark required forced end settlement.

The independent checker reconciles mark arithmetic and trade identity, not a
second implementation of signals or full protective-fill chronology. The runner
does not apply the complete Atlas evaluation/funded/payout rule chain. There is
no tick, native MT5, or prospective demo order reconciliation. Five trades with
PF near 1 offer **no defensible profitability conclusion**.
