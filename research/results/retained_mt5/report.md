# Retained XAUUSD strategies in MT5 Strategy Tester

Each strategy and the combined book ran as a tester-only MQL5 Expert Advisor, using native market orders and server stops on real bid/ask ticks. Each period started a fresh $5,000 evaluation. After a pass the native tester started a fresh 1:50 funded account on the next trading date. There were eight evaluation runs and eight funded runs. New York Session Reversal was excluded.

Net P&L, PF, wins and drawdown below describe the unrestricted MT5 evaluation run across the entire period, including trades after the historical evaluation would have ended. The final columns apply the Access rule model to the native funded deals. Periods are January–October 2026 and January–December 2025.

| Period and MT5 report | Net P&L | PF | Wins / trades | Max equity DD | Evaluation pass UTC | Funded outcome | Modeled cash payout | Cash after entry and activation |
|---|---:|---:|---:|---:|---|---|---:|---:|
| [2026 Asian Range Filtered](2026_filtered.htm) | +$428.02 | 1.95 | 15/26 | 3.04% | 2026-05-05 | [inactivity breach 2026-10-23](2026_filtered_funded_audit.json) | $0.00 | -83.00 |
| [2026 Asian Breakout](2026_breakout.htm) | +$390.90 | 1.38 | 15/31 | 8.06% | 2026-02-04 | [inactivity breach 2026-10-28](2026_breakout_funded_audit.json) | $0.00 | -83.00 |
| [2026 London Momentum Tight](2026_london.htm) | +$576.58 | 1.57 | 22/51 | 6.25% | 2026-03-19 | [trailing breach 2026-07-07](2026_london_funded_audit.json) | $0.00 | -83.00 |
| [2026 Three-strategy portfolio](2026_portfolio.htm) | +$957.60 | 1.52 | 39/82 | 9.37% | 2026-02-06 | [trailing breach 2026-03-30](2026_portfolio_funded_audit.json) | $0.00 | -83.00 |
| [2025 Asian Range Filtered](2025_filtered.htm) | +$554.20 | 2.18 | 28/47 | 2.83% | 2025-05-12 | [Active at cutoff](2025_filtered_funded_audit.json) | $100.00 | +17.00 |
| [2025 Asian Breakout](2025_breakout.htm) | +$697.08 | 1.96 | 28/52 | 2.80% | 2025-04-16 | [Active at cutoff](2025_breakout_funded_audit.json) | $0.00 | -83.00 |
| [2025 London Momentum Tight](2025_london.htm) | +$465.05 | 1.60 | 27/70 | 2.82% | 2025-10-17 | [Active at cutoff](2025_london_funded_audit.json) | $0.00 | -83.00 |
| [2025 Three-strategy portfolio](2025_portfolio.htm) | +$956.73 | 1.75 | 55/119 | 4.20% | 2025-04-21 | [Active at cutoff](2025_portfolio_funded_audit.json) | $100.00 | +17.00 |

In 2025 the filtered strategy and the combined portfolio each modeled one $100 payment on their separate accounts. That leaves $17 after the standard $5 entry fee and $78 activation charge in each scenario. No trader cash was actually paid. All four funded paths breached in 2026. The three-strategy portfolio hit its first Atlas Protector trigger on March 23 and breached trailing equity on March 30 before collecting a payout.

The test symbol cloned the Exness demo contract. Native MT5 charged no commission on these runs and used its own financing and fill prices. The original Python test modeled adverse slippage, commission and financing. All strategy entry directions and millisecond timestamps matched. One May 2026 London trade accounted for $91.94 of the $107.20 difference in the 2026 portfolio result. MT5 suspended stop execution during the cloned symbol’s closed session, while the Python model filled on a quoted bid. The exact historical Atlas session is unknown.

The MT5 deal reports and fills are native. Atlas loss limits, inactivity, deductions, fees and payout eligibility are a separate historical model applied to those fills. The funded EA also executed the modeled Protector liquidation. Historical Atlas trading conditions and the complete all-currency high-impact news restrictions were unavailable. The modeled payouts assume eligibility and prompt settlement. The settings and choice of retained strategies were already informed by historical research.

[Download individual and portfolio trade ledgers](native_trade_records.csv) · [Session probe](session_sensitivity.md) · [Entry reconciliation](entry_parity.json) · [MQL5 Expert Advisor](../../mt5_retained/RetainedAtlas.mq5) · [Atlas Access rules](https://help.atlasfunded.com/access) · [Fees](https://docs.atlasfunded.com/refunds)
