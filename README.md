# Ultra Core | XAUUSD trading research on MT5

Ultra Core tests gold strategies, reconciles native MetaTrader 5 fills, and models the path from a $5,000 Atlas Access evaluation to eligible withdrawals. **The current research candidate is Asian Range Filtered + London Momentum Tight for forward demo testing. Funded deployment remains unapproved.** The checked-in runtime still uses the four-strategy configuration documented in the operations runbook. [Research roster](research/results/guarded_retained_mt5/payout_roster.json) · [Runtime and VPS runbook](docs/OPS_RUNBOOK.md)

## What the MT5 records show

The native batch completed **69 evaluation and funded phase runs**, including **37 funded runs**, on Exness Standard XAUUSDm bid/ask ticks. The annual windows were January–December 2025 and January–October 2026. The phased policy traded 0.02 lots in evaluation. It restarted with a fresh funded balance, traded 0.01 lots with one position at a time, and attached a broker-visible stop. November 2026 remains the reserved holdout. [Run index and individual trade ledgers](research/results/guarded_retained_mt5/report.md) · [Native tester source](research/mt5_retained/RetainedAtlas.mq5)

| Two-strategy portfolio, January evaluation start | Funded trading P&L | Profit factor | Wins / trades | Max modeled funded equity drawdown | First modeled receipt | Cash after fees |
|---|---:|---:|---:|---:|---|---:|
| 2025 | +$350.76 | 1.77 | 37 / 80 | 1.76% | $100 on Oct 28 | +$17 |
| 2026 through October | +$317.05 | 1.59 | 29 / 59 | 3.54% | $100 on Oct 19 | +$17 |

[2025 native MT5 report](research/results/guarded_retained_mt5/2025_portfolio_funded_mask5_phase_split_m01d01x5.htm) · [2025 payout audit](research/results/guarded_retained_mt5/2025_portfolio_funded_mask5_phase_split_m01d01x5_audit.json) · [2026 native MT5 report](research/results/guarded_retained_mt5/2026_portfolio_funded_mask5_phase_split_m01d01x5.htm) · [2026 payout audit](research/results/guarded_retained_mt5/2026_portfolio_funded_mask5_phase_split_m01d01x5_audit.json)

- **Start date changed the result.** Eight fresh quarterly starts produced four modeled $100 payouts, three funded accounts still unpaid, and one evaluation still active at cutoff. Zero breaches were observed under the modeled rules. Receipts of $400 minus seven $83 activated attempts and one $5 entry-only attempt left **−$186 total, or −$23.25 per attempt by cutoff**. The scenarios overlap and later starts had less time to pay. [Quarterly records](research/results/guarded_retained_mt5/report.md) · [Payout decision](research/results/guarded_retained_mt5/payout_decision.md)
- **The continuous account paid infrequently.** Carrying the April 2025 funded account through October 2026 generated +$626.42 of native trading P&L and two modeled $100 receipts, 356 days apart. Modeled cash after one set of fees was **+$117**. [Continuous funded ledger](research/results/guarded_retained_mt5/2025_portfolio_funded_mask5_phase_split_continuous_audit.json)
- **The third strategy improved timing.** Adding Asian Breakout brought the 2026 January-start payout forward by 20 days. Both portfolios produced four receipts across the eight quarterly starts. At an added $1 per 0.01-lot round trip, both portfolios lost the January-start payouts in both years. [Portfolio comparisons and cost sensitivity](research/results/guarded_retained_mt5/payout_decision.md)
- **Luna failed.** The revised Luna executable lost $412.71 with PF 0.75 in the 2026 test. In a separate matched native funded comparison, the retained portfolio with the Luna signal follower breached trailing drawdown before paying. [Luna MT5 report](research/results/luna_payout_candidate/report.md) · [Joint-account comparison](research/results/mt5_joint/report.md)

**Actual cash received was $0.** MT5 supplied fills and trading P&L. The payout ledger applies the modeled Atlas rules and fees to those fills. The test used previously explored dates, broker-specific costs, and a partial historical news calendar. Broker-specific Atlas costs and full event coverage are needed before relying on these payout estimates. [Robustness results](research/results/guarded_retained_mt5/robustness.json) · [Execution audit](docs/BACKTEST_REALITY_AUDIT.md) · [Atlas payout rules](https://help.atlasfunded.com/access)

**Earlier-year check without Luna.** Both portfolios lost money in 2022 and 2023 and stayed in evaluation. Both passed in 2024, then lost money once funded. Across the six January-start portfolio attempts, modeled payouts totaled $0 and cash after fees totaled −$186. [2022–2024 MT5 reports and individual strategy results](research/results/retained_early_years/report.md)

## Code and verification

| Path | Purpose |
|---|---|
| `src/core/` | MT5 runtime, order gates, account state, and trade logs |
| `src/strategies/portfolio_atlas.py` | Existing runtime strategy configuration |
| `src/backtesting/` | Historical execution engine. Requires M1 coverage by default |
| `src/atlas/` | Account-rule engine. See the rule verification notes before account use |
| `research/mt5_retained/` | MT5 tester-only EA and PowerShell runner |
| `research/results/` | Native reports, chronological deal exports, and account audits |
| `scripts/demo_release.py` | Hash-verified release staging and code rollback snapshots |

~~~powershell
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pytest tests/ -q
.\venv\Scripts\python.exe -I scripts/validation/prereg_check.py
~~~

GitHub CI runs the Python suite and checks recorded research provenance. Native MT5 reproduction requires a dedicated Windows demo tester and the archived bid/ask data. [CI workflow](https://github.com/rohith95-p/trading-platform/actions/workflows/ci.yml) · [Quote archive documentation](research/xauusd_archive/README.md) · [Atlas rule verification](docs/ATLAS_RULES_VERIFICATION.md)

## VPS staging

The updater prepares a pinned release from a local GitHub revision ZIP, the exact 40-character commit, and the verified SHA-256 of that ZIP. Activation is a separate operations step. Preserve account state and review the documented migration before an upgrade. Store credentials in the local `.env.local` file. [Staging commands](docs/OPS_RUNBOOK.md#stage-a-pinned-vps-release) · [Atlas state recovery](docs/ATLAS_STATE_RECOVERY.md) · [Deployment readiness](docs/DEPLOYMENT_READINESS.md)
