# Aurion LowRisk in local MetaTrader 5

The input archive contained one proprietary MT5 Expert Advisor and one LowRisk preset. The shipped preset disables `AIDecision` and uses 0.01 lots for the first entry, multi-level basket recovery, hidden stop settings and a maximum drawdown input of 20.0. The vendor describes Aurion as a multi-level M15 strategy for gold. Specific entry rules are inside the executable. [Aurion manual](https://xaubot.com/xaubot-aurion-guide/)

The original executable ran in the local MT5 Strategy Tester on Exness Standard XAUUSDm real bid/ask quotes, with separate $5,000 starting balances. The evaluation used 1:100. A separate post-pass stress test used fresh 1:50 funding. No trades were sent to a broker account. Native MT5 P&L and the Atlas rule replay answer different questions. Atlas had no access to these simulated accounts.

## Evaluation results

| Window | Native net P&L | PF | Wins / trades | Maximum equity drawdown | First modeled evaluation outcome |
|---|---:|---:|---:|---:|---|
| [2025](aurion_2025_evaluation.htm) | −$692.00 | 0.59 | 243 / 369 | 20.36% | [Passed on February 20](aurion_2025_evaluation_audit.json) |
| [January–October 2026](aurion_2026_evaluation.htm) | −$822.02 | 0.49 | 110 / 145 | 20.09% | [Daily-loss breach on January 29](aurion_2026_evaluation_audit.json) |

The 2025 and 2026 native reports processed 76,283,540 and 80,478,503 ticks, respectively. Both matched the archived quote counts. The 2025 evaluation reached the $150 target before the native full-window run lost money. The 2026 evaluation crossed the daily floor at 15:28 UTC on January 29, about 13 minutes after the preceding fill. Quote-marked equity was $4,858.83 against the approximately $4,860.68 modeled daily floor. The later $150 target on February 3 had no effect on that attempt.

## Order-level evidence

The preset's 0.01-lot initial entry expanded to a largest order of **0.64 lot** in 2025 and **0.32 lot** in 2026. The largest aggregate open sizes were **1.28** and **0.64 lots**. Quote-marked floating losses reached **$1,172.67** in 2025 and **$1,075.27** in 2026.

All **514 evaluation entries** were submitted without a broker-visible stop. In the two evaluation replays, 125 winning trades closed in less than three minutes, accounting for $477.44 of gross gains. In a funded scenario Atlas can deduct gains from these rapid trades and can breach an account when at least 80% of its trades lack stop losses. The counts above come from the evaluation reports. [Atlas stop-loss rule](https://help.atlasfunded.com/stop-loss) · [Atlas short-trade deductions](https://help.atlasfunded.com/short-trades)

## Fresh 2025 funded replay

The February 21 fresh funded run at 1:50 processed 67,935,139 verified real ticks. It lost **$789.83**, had PF **0.43**, won 151 of 227 trades (66.5%), and reached **20.23%** native equity drawdown. All 227 entries lacked a broker-visible stop. The best closed-profit day made **$12.68** before simulated deductions. Zero days reached the $25 qualifying-day minimum.

On April 16 at 01:02:32.785 UTC, the $5,178.17 balance was marked at $5,078.11 equity, enough to trigger Atlas Protector. The first trigger would close the positions and reduce the split to 50%. The original EA continued in the tester, so the later native daily and trailing crossings describe unchanged orders. An Atlas liquidation would change that path. There was **no eligible payout on the verified path before Protector**, and even the unchanged full-window run had zero qualifying days. Actual payouts were $0. The 2026 evaluation breach prevented a funded replay. [2025 funded MT5 report](aurion_2025_funded.htm) · [Funded quote audit](aurion_2025_funded_audit.json) · [Atlas Access terms](https://help.atlasfunded.com/access)

**Decision.** The supplied Aurion preset fails the after-cost profit-factor screen in both evaluation windows and failed to produce an eligible Atlas payout in the tested funded path.

## Evidence

- [Frozen test protocol](../../registry/PREREG_AurionMT5Trial_2026-11-21.md)
- [Native tester launcher](../../../scripts/research/aurion_native_trial.py)
- [Quote and trade ledger auditor](../../../scripts/research/aurion_trial_audit.py)
- [2025 native deal export](aurion_2025_evaluation.csv)
- [2026 native deal export](aurion_2026_evaluation.csv)
- [2025 funded native deal export](aurion_2025_funded.csv)
