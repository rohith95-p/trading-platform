# Native MT5 cross-check of three XAUUSD strategies

Each year starts with a fresh $5,000 Access evaluation. A verified evaluation pass starts a new $5,000 funded simulation on the next trading date, at MT5 leverage of 1:50. The January–October 2026 and full-calendar 2025 windows use the same Exness quote archive as the Python tests.

| Year | Book | Phase | Trades | Native net | Native PF | Native with ECN assumptions | Python net | First account event | Conditional cash |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| 2025 | breakout | evaluation | 52 | +697.08 | 1.96 | +691.67 | +690.99 | passed 2025-04-16 | 0.00 |
| 2025 | breakout | funded | 38 | +527.68 | 1.90 | +524.10 | +523.84 | active at cutoff | 0.00 |
| 2025 | filtered | evaluation | 47 | +554.20 | 2.18 | +548.11 | +548.00 | passed 2025-05-12 | 0.00 |
| 2025 | filtered | funded | 35 | +383.70 | 2.00 | +379.09 | +378.76 | active at cutoff | 100.00 |
| 2025 | london | evaluation | 70 | +465.05 | 1.60 | +455.54 | +456.08 | passed 2025-10-17 | 0.00 |
| 2025 | london | funded | 17 | +306.42 | 2.28 | +304.12 | +304.29 | active at cutoff | 0.00 |
| 2025 | portfolio | evaluation | 119 | +956.73 | 1.75 | +940.83 | +941.18 | passed 2025-04-21 | 0.00 |
| 2025 | portfolio | funded | 87 | +753.61 | 1.74 | +741.95 | +741.89 | active at cutoff | 100.00 |
| 2026 | breakout | evaluation | 31 | +390.90 | 1.38 | +386.49 | +386.30 | passed 2026-02-04 | 0.00 |
| 2026 | breakout | funded | 27 | +306.51 | 1.40 | +302.74 | +302.46 | inactivity breach 2026-10-28 | 0.00 |
| 2026 | filtered | evaluation | 26 | +428.02 | 1.95 | +424.75 | +422.22 | passed 2026-05-05 | 0.00 |
| 2026 | filtered | funded | 18 | +237.78 | 1.74 | +235.50 | +233.15 | inactivity breach 2026-10-23 | 0.00 |
| 2026 | london | evaluation | 51 | +576.58 | 1.57 | +569.76 | +476.14 | passed 2026-03-19 | 0.00 |
| 2026 | london | funded | 41 | +391.92 | 1.50 | +386.52 | +294.01 | trailing breach 2026-07-07 | 0.00 |
| 2026 | portfolio | evaluation | 82 | +957.60 | 1.52 | +946.57 | +850.40 | passed 2026-02-06 | 0.00 |
| 2026 | portfolio | funded | 72 | +912.47 | 1.63 | +902.99 | +806.43 | trailing breach 2026-03-30 | 0.00 |

## Interpreting the figures

Trading P&L includes the full tester interval. An Atlas attempt ends at its first breach. Evaluation profit does not enter the funded account. A funded row with conditional cash assumes verified KYC and immediate approval and settlement. Deduct $5 entry and $78 activation once per activated attempt to obtain modeled cash after fees. The $100 cash receipt corresponds to $111.11 gross debited for the usual 90% split. After the first Protector liquidation the split drops to 50%. A second trigger breaches the account.

Native fills are grouped by position ID and reconcile to the official tester deal list and terminal net profit. Marks use ordered Exness bid for longs and ask for shorts, entry-side native fees and native reported swap across accrued UTC rollovers. The ECN sensitivity reprices each original MT5 fill by $0.020 per ounce on entry and stop/market exits, $3.50 round-trip per lot commission and the original project financing model. It holds the MT5 exit decisions fixed. The independent Python strategy run can make different exits. The full unrestricted equity drawdown is stored alongside MT5’s own report drawdown.

The matched-entry check uses strategy magic, UTC entry minute, direction and within-minute occurrence. Native and Python stop/target decisions can differ inside a session boundary. In the 2026 London long opened May 5 at 12:15 UTC, the static cloned MT5 Tuesday session closed from 21:58 to 23:00 UTC. All 2,073 sub-stop quotes in the probe occurred inside that closure. Python filled its stop at 22:07 and MT5 held the position until a take-profit after reopening. The actual historical Atlas session is unavailable. [Session probe](native_session_probe_20260505.csv)

Published current Access rules are applied retrospectively. Funded paths include known news restrictions, short-trade deductions, observed Protector liquidations, daily equity resets, trailing floors, inactivity, funded margin checks, 28-day/14-day windows, 3 qualifying $25 days, and the 20% consistency test. The archived news set covers selected USD releases only. Atlas restricts all currencies’ high-impact events. Results and payouts are scenario estimates. No money was paid or received. [Access terms](https://help.atlasfunded.com/access) · [Payout windows](https://help.atlasfunded.com/payouts) · [News rules](https://help.atlasfunded.com/news-trading)

[Full comparison and event times](native_comparison.csv). The native HTM reports, millisecond deal CSVs, matched-fill CSVs and per-run audit JSONs are in this folder.
