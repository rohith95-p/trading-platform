# Atlas Access rules verification — 18 November 2026

## Scope and status

This review concerns **Atlas Funded CFD/Forex Access**, at atlasfunded.com, for a prospective $5,000 MT5 account. It does not cover Atlas futures, another firm's similarly named program, or a grandfathered contract. No account was bought or accessed. Public documents were checked on 18 November 2026; the signed agreement and account-specific dashboard still need reconciliation before use. Production settings have not been changed.

**The current model is not certified against these rules.** Several current public provisions differ materially from repository assumptions. Atlas describes both evaluation and funded accounts as simulated, with cash rewards; funded does not mean the user's orders enter a live market. [Terms, updated 12 November 2026](https://www.atlasfunded.com/terms)

## Access-specific conditions

| Item | Evaluation | Funded |
|---|---|---|
| Closed-balance target | 3%; $150 at $5K | None |
| Equity-trailing maximum loss | 10% | 6% |
| Daily loss | 5% | 3% |
| Minimum days | None | 3 qualifying days per payout, each at least 0.5% |
| Best-day consistency | None | 20% |
| MT5 leverage | Up to 1:100 | 1:50 |
| Payout timing | None | First 28 days, subsequent 14 days |
| Standard split / minimum profit | N/A | 90% / $100 |

Access begins with a $5 evaluation payment (some $1 offers); the funded activation price is shown at checkout and remains unverified here. Activation is offered for 14 days after passing. Both phases have a 30-day inactivity condition. [Access-specific table](https://help.atlasfunded.com/access)

## Loss calculations and cash-flow implications

The published maximum-loss formula is `peak_equity * (1 - loss_rate)`. The peak includes unrealized profit and does not fall when a winner reverses. It keeps trailing above starting capital. After a payout, Access is re-anchored to the remaining balance. At $5K the initial funded floor is $4,700; after equity peaks at $5,200 it is $4,888. These are arithmetic examples, not simulated results. [Maximum drawdown](https://help.atlasfunded.com/max-drawdown)

Daily floor is `equity_at_00UTC * (1 - daily_rate)`, fixed until the next UTC reset. Today's profit does not raise today's daily floor. Profit-rule deductions cannot cause a daily breach, and a payout reduces the daily floor by the paid amount. A simulator must distinguish trading loss, deductions and payouts. [Daily loss](https://help.atlasfunded.com/daily-loss)

Consistency is `best_closed_profit_day_since_account_open / net_closed_profit_since_last_payout <= 0.20`. The lifetime best day survives a payout; the denominator restarts. Exceeding this blocks payout rather than breaching the account. Pre-11-November funded accounts retain their signed limits. [Consistency](https://help.atlasfunded.com/consistency)

**Derived constraint:** at an unchanged $5K qualifying-day anchor, a qualifying day is at least $25. The best day is therefore at least $25, requiring at least $125 cycle profit under 20% consistency. With a $40 lifetime best day the requirement becomes $200 in every later cycle. Consequently $111.11 gross, the approximate profit debit needed to receive $100 at 90%, is not automatically payout-eligible. Eligibility amount and requested withdrawal are different quantities; residual profit, re-anchoring, later cycles and contract rounding must be modeled explicitly.

The dashboard additionally checks active funded status, no pending payout, positive account profit, open payout window, qualifying days, threshold and KYC. Requests are not automatic payments. [Eligibility checklist](https://help.atlasfunded.com/payout-eligibility)

## Funded protections

| Rule | Current public description | Research consequence |
|---|---|---|
| Protector | Net open loss reaches 2% of initial balance; closes all. First hit permanently reduces split to 50%; second hit breaches. | At $5K, $100 combined floating loss can trigger even if closed balance is profitable; preserve lifetime hit count. |
| News | Red-folder events; ±5 minutes applies to every instrument. Profitable flagged trades lose their profit; opening inside can cause automatic closure. | USD-only calendar may omit applicable events; account dashboard restriction list is authoritative. |
| Short trades | Profit from holding under 3 minutes is removed; losses remain. Partial closes are relevant. | Evaluate deductions per execution leg, without disabling protective stops. |
| Margin | `used_margin/(used_margin+free_margin) >= 80%` closes positions and deducts winning profit; no automatic breach. | Require verified MT5 instrument margin and account leverage. |

Sources: [Protector](https://help.atlasfunded.com/atlas-protector), [news](https://help.atlasfunded.com/news-trading), [short trades](https://help.atlasfunded.com/short-trades), [margin](https://help.atlasfunded.com/margin-usage). These dedicated pages describe these protections as funded-only; do not silently rewrite the owner's existing more conservative evaluation policy.

EAs are publicly permitted; funded behavior must comply with the same restrictions. A funded account with 80% or more trades lacking stops can be breached under the documented excessive-risk rule. [FAQ](https://help.atlasfunded.com/faq)

## Contradictions and local implementation gaps

1. The [program comparison](https://help.atlasfunded.com/programs) still shows Access consistency 40%, while Access, consistency and FAQ pages show 20%. Use both in sensitivity analysis; use 20% as the provisional new-account specification and obtain an account-specific binding rule record before deployment.
2. Some pages retain a 26 October review label while discussing grandfathering at 11 November. Review labels are not sufficient version control. The older [docs.atlasfunded.com risk overview](https://docs.atlasfunded.com/drawdown-risk), labeled July, is not interchangeable with current help pages.
3. `src/atlas/rules.py` currently defaults payout consistency to 40%, uses peak minus a fixed initial-balance drawdown allowance, and rolls a daily reference from a previous day's high. These differ from the current dedicated formulas. This is a documented mismatch, not authorization to alter live safety settings.
4. `src/backtesting/access.py` uses percentage peak/daily floors but delegates payout eligibility to the old 40% helper and clears daily records at withdrawal, losing lifetime best-day information. It also lacks full Protector, deduction, margin, pending-payment and approval state. Earlier payout studies are scenario approximations, not current Access qualification.
5. Exact XAUUSD symbol, lot increment, contract size, point/tick size, spread distribution, commissions, swap/triple day, stop/freeze distance and real demo fills have not been verified against a purchased Atlas account. Exness/Dukascopy observations cannot supply those specifications.

## Next executable engineering step

Build an explicitly versioned **experimental** Access rule profile with source dates and the above cash-flow states, then test synthetic boundary cases and historical paths. Preserve production rules until the owner separately authorizes any live-setting change. Obtain checkout/agreement/dashboard values and broker-demo specifications before labeling an evaluation or funded simulation representative. No provider support message has been sent.

## Experimental ledger implemented

`src/research/access_rules_20261118.py` now supplies a standalone, frozen-source research profile and supplied-event ledger. It imports no production rule or execution module and does not replace `src/backtesting/access.py`. `tests/test_access_rules_20261118.py` tests deterministic synthetic accounting paths only; no market-price evaluation or holdout use is involved.

Modeled: percentage trailing equity floors; exact supplied midnight equity daily anchors; below-floor breach checks; evaluation closed-profit target; UTC realized-P&L daily netting; three qualifying days; 20% lifetime-best-day consistency; first/subsequent 28/14-day timing; permanent Protector split reduction and second-hit breach; explicit payout request, pending state, supplied approval/rejection and settlement; gross-to-cash cent rounding; payout drawdown/profit re-anchoring. Identity verification and known flat positions are mandatory for requests. The lifetime best day survives settlement, while cycle P&L/day records reset.

Important interpretation limits: qualifying-day and Protector thresholds retain original initial balance; the eventual agreement must confirm their anchors after payouts. Only weekday payout requests are admitted as a conservative scenario assumption, pending contract/dashboard confirmation. A $100 cash request at 90% reserves $111.11 gross with half-up cent rounding; actual provider rounding is unverified. Residual earned balance becomes the new profit anchor after settlement. This is a specific scenario interpretation, not certification of provider bookkeeping.

Not modeled: quote/fill generation; continuous unobserved equity; actual Protector liquidation prices; margin close-outs; news/short-trade deductions and their rule-specific floor exemptions; inactivity; contract specifications; payout fees/caps; processing delays; account-specific grandfathering/add-ons; KYC approval processes or firm discretion. Protector detects the supplied floating-loss threshold but requires the caller to supply resulting close fills. A pending payout never settles automatically. Every UTC reset must be supplied separately; missing midnight equity is rejected rather than estimated. Callers must supply after-cost closed P&L and all relevant equity observations, including peaks and adverse excursions. Passing these unit tests demonstrates the declared ledger behavior, not historical profitability or full Atlas compliance.
