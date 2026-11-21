# XAUUSD demo Telegram messages

All timestamps are IST. Dollar balances and risk limits refer to the virtual evaluation. Every fill is tied to an MT5 deal.

| Message | What it says |
| --- | --- |
| **Evaluation started** | Evaluation started. Waiting for the XAUUSD market to open. Includes the attempt number, virtual balance, target, equity peak, UTC daily anchor and open-position count. |
| **Evaluation active** | Evaluation active. Includes the current virtual evaluation figures. |
| **Entry filled** | Strategy, buy or sell position, lots, fill price, cash impact of this fill, timestamp and MT5 deal number. |
| **Exit filled** | Strategy, original position side, exited lots, fill price, cash impact of this fill, timestamp and MT5 deal number. |
| **Evaluation account breached** | Attempt number and reason. Includes virtual balance, equity, equity floor where applicable and the number of open positions. New entries stopped. A fresh attempt starts when the demo is flat and verified, within the test window. |
| **Fresh evaluation started** | Attempt number, virtual balance of $5,000 and $5,150 target. Previous breach remains recorded. Demo positions and pending orders are clear. |
| **Evaluation target reached** | Evaluation target reached. New entries stopped. Funded and payout checks are separate. |
| **Evaluation entry window closed** | Evaluation entry window closed. Includes the last available virtual evaluation figures. |

The breach reasons are **daily equity loss limit**, **trailing equity loss limit** and **30-day inactivity limit**. If the journal write fails, the status message still identifies the breach and says that a fresh demo attempt requires a flat, verified account.

## Trading issues

- **MT5 terminal unavailable**
- **EA status missing or stale**
- **EA start has not been confirmed**
- **MT5 automated trading permission is off**
- **MT5 deal history unavailable**
- **Expected demo account could not be verified**
- **Evaluation start could not be verified. Entries blocked.**
- **EA run identity could not be saved. Entries blocked.**
- **EA restarted. Account reconciliation required.**
- **Unexpected position. Entries blocked.**
- **Unexpected pending orders. Entries blocked.**
- **Midnight equity unverified. Entries blocked.**
- **Connection lost with exposure. Entries blocked.**

Format previews are headed **TEST ONLY · XAUUSD demo message formats**. They state that no trade, breach or reset occurred.
