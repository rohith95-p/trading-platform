# Minute chronology engineering correction

Synthetic regression contract fixed and committed before implementation or tests.
No historical strategy evaluation, optimization, live code or holdout data.

At each M1 open, only the opening bid/reconstructed ask and previously completed
history may affect entry caps, account cash, margin or risk decisions. Existing
protective exits known at the open may settle first; later intraminute extrema
may not free a position slot or change entry sizing at the earlier open.

After entry decisions and open-quote management, walk the minute range once for
each eligible position, including newly opened orders. Market stops must continue
working even if the scan is skipped for spread, news, downtime or account gates.

Explicit legacy chronology may reproduce old studies but must be identified by
configuration. Preserve the earlier diagnostic default that subminute delayed
prices require tick data; do not invent intraminute quote timestamps.

Pass criteria: synthetic old-position exits later in the minute do not release a
slot or future realized profit to a new open-time decision. True opening gaps may
settle before entry. Entry-minute stop/target checks happen once and remain active
on skipped scan branches. Existing offline regressions must be reviewed for
intentional chronology differences; never relax a test to conceal leakage.

## Follow-up engineering criteria, fixed before implementation

Realized P&L must reach the next scan's daily loss gate immediately after a
known protective fill, rather than wait until the end of its containing M15
candle. Retain the existing IST exit-date attribution. A synthetic loss followed
by another signal inside the same M15 must block on the next minute when the
configured daily limit is breached. Verify IST-midnight attribution independently.

The exported equity path must explicitly identify itself as `closed_balance`
and state that floating drawdown is unverified. Do not infer intraminute
mark-to-market equity from unavailable tick order.
