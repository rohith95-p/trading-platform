# XAUUSD joint native MT5 signal-follower experiment

The original Luna executable runs on a separate historical signal account. The joint tester consumes only basket-open direction and basket-flat notifications from that source. Source order size, fills and realized P&L are never copied. Each notification becomes available after the end of its printed second. The joint tester makes native orders against the next observed real quote. It ignores late entries over 60 seconds old and every additional grid order. A simulated live architecture would require a separate signal account, an event bridge and authorization to copy between those accounts.

The joint account starts at $5,000. The three retained signals calculate from closed bars inside MT5. At equal timestamps the retained signals get first priority. Either sleeve can occupy the only position. Luna receives 0.01 lot and a $30 initial stop per ounce with $5 risk reserve. The retained sleeve uses its own ATR stop within the same dollar cap. The shared guard attempts liquidation at $60 floating loss. Start-of-tester state is flat; no source inventory carries into a fresh account. No EA was attached to a live chart.

The log records a zero return from ChartOpen in the nonvisual local Strategy Tester. No second chart was available to attach a template. MetaQuotes also documents that applying an EA template to the running chart unloads its previous EA. The results therefore test the alternative copier, with native broker execution, shared positions and margin. They do not reproduce the original closed-source EA making decisions from the joint account. [MetaQuotes ChartApplyTemplate](https://www.mql5.com/en/docs/chart_operations/chartapplytemplate)

The original-overlap diagnostic compares two independently recorded books by exposure interval, using timestamps from Luna's native report at one-second resolution. This diagnostic measures historical collisions only. Joint P&L always comes from actual orders on one native tester account. Native demo costs use Exness Standard. A second cost calculation applies the project's ECN stress assumption. The native funded ruler checks every archived quote for a Protector crossing independently of the EA.

The comparison cutoff is November 1, 2026 UTC, exclusive. Positive combined return, PF at least 1.3, eligibility for a $100 net receipt under modeled Atlas terms, and no historical breach are required. The funded run begins the first trading day after the observed evaluation pass. The original underlying source account has pre-2026 trading history. Both evaluation and funded follower accounts start fresh. These periods have been seen during previous research.

## 2026 decision

| Fresh $5,000 evaluation book, January–October | Native trades | Wins | Net | PF | Evaluation | Funded cash received | Cash after fees |
|---|---:|---:|---:|---:|---|---:|---:|
| [Retained signals without Luna](../guarded_retained_mt5/2026_portfolio_audit.json) | 71 | 32 | $282.34 | 1.405 | Passed September 14 | $0 | −$83 |
| [Retained signals plus Luna follower](joint_2026_7_evaluation_audit.json) | 554 | 418 | $224.02 | 1.138 | Passed September 17 | $0 | −$83 |
| [Luna follower alone](joint_2026_0_evaluation_audit.json) | 516 | 409 | −$94.74 | 0.910 | Still below target at cutoff | $0 | −$5 |

Adding Luna reduced full-window native net by $58.32 and delayed the evaluation pass three calendar days. Inside the account, Luna contributed −$46.73 on 486 trades, PF 0.951. Asian Range Filtered contributed $179.12 on 24 and London $91.63 on 44. Asian Breakout contributed zero filled trades. The shared controller blocked 25 opposing Luna entry attempts and discarded 207 additions to open Luna grids. It never exceeded one open position. Applying project ECN costs to the 554 native trades reduced net to $183.07, PF 1.112. In an independent-book collision diagnostic, 34 of 82 legacy retained positions overlapped opposite original Luna exposure in 2026, and 54 of 119 in 2025. These are exposure intervals, not blocked-order counts.

The [fresh joint funded book](joint_2026_7_funded_audit.json) started September 18 at 1:50. Its 64 full-window trades made $68.25 in MT5. After $44.89 of modeled profit deductions, funded equity finished at $5,023.36 with three qualifying days. Maximum observed floating loss reached $30.01 across the tick audit. The account survived through October 30, earned no modeled withdrawal, and incurred $83 in modeled attempt fees. There is no time to first payout. The ECN stress overlay on that same funded start also yielded zero payouts. First evaluation pass under ECN costs was September 28, so the funded stress result is a sensitivity comparison for the native handoff, not a fully independent ECN lifecycle.

The joint run failed the PF and payout requirements. The Luna signal follower also failed standalone. Full 2025 replay of this new configuration was screened out by the 2026 gate. This result applies to the frozen tested architecture. Actual money received was zero.

[Per-trade records, joint evaluation](joint_2026_7_evaluation_trades.csv) · [Joint funded trades](joint_2026_7_funded_trades.csv) · [Luna follower alone](joint_2026_0_evaluation_trades.csv) · [Collision counts](joint_2026_7_evaluation_journal.txt) · [Archived book overlaps](original_overlap.json)

## Matched funding date

The phase-specific experiment used the retained 0.02-lot evaluation, which passed February 6. Both comparisons then started a fresh $5,000 funded account on February 9 using the same 0.01-lot controls. This isolates the funded-stage effect of enabling the Luna source.

| February 9 to October 30, 2026 | Full-window trades / wins | Full-window MT5 net | PF | First funded breach | Modeled cash received | Cash after fees |
|---|---:|---:|---:|---|---:|---:|
| [Retained only](../guarded_retained_mt5/2026_portfolio_funded_phase_split_audit.json) | 64 / 31 | $346.69 | 1.578 | Active at cutoff | $100 on September 29 | +$17 |
| [Retained plus Luna follower](phased_2026_7_funded_audit.json) | 469 / 353 | $274.21 | 1.200 | Trailing drawdown, July 2 | $0 | −$83 |

With Luna, modeled trailing drawdown reached 6% at 13:50:22 UTC on July 2. The audit applied $267.97 in profit deductions before the breach. Maximum floating loss reached $30.24. The 2% floating Protector did not trigger. The positive full-window MT5 result includes orders after the account had already failed. Adding Luna reduced payouts by $100 and full-window net by $72.48. Luna contributed −$60.89 on 408 trades, with 24 opposing entries blocked and 186 additional grid orders ignored. Every open position carried a stop and the joint ledger never exceeded one position. ECN-stressed results also breached on July 2. The later September funded handoff survived to cutoff because it began after the July breach. Both comparisons reject this Luna sleeve.

[Matched native joint trade ledger](phased_2026_7_funded_trades.csv) · [Native tester report](phased_2026_7_funded.htm) · [Joint controller counts](phased_2026_7_funded_journal.txt)
