# Independent broker quote archive check

Keep the date, order fixtures, stops, targets, costs and comparison code from TickReconciliation protocol 69fc353. Test whether the published Exness historical quote archive can supply the same pre-holdout hour on a different feed. Use XAUUSD Raw Spread for January 2025, retaining only January 6 at 12:00–13:00 UTC. Freeze the original zip SHA256, CSV identity, selected rows, time and spread checks. Keep the original archive local. Do not use other intervals to select a result. If unavailable, record the failure. Two diagnostic orders do not constitute an alpha test. Different providers and account types may publish different quotes. No terminal connection is required.

Exness describes its historical bid and ask archive and account-type suffixes at [Tick history](https://get.exness.help/hc/en-us/articles/360021547851-Tick-history).
