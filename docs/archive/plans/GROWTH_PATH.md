# Account Growth Path & Sizing Ladder

## The Goal
The primary milestone is achieving a **$10/day net profit** on average.

## Account Type Decision
* **Standard vs Cent/Micro:** We will remain on a **Standard MT5 Account**.
* **Rationale:** The broker's 0.01 lot minimum on a standard account provides the correct dollar-per-point sizing to hit the $10/day goal with the current Portfolio V4 strategies (FVGNYTight, etc.). Moving to a cent account would require 100x the points captured to meet the dollar goal, which is unrealistic.

## Risk Mitigation
Since 0.01 lots on a standard account represents a higher percentage risk on a smaller balance (~15-20% of a $100 balance per trade initially):
1. **Circuit Breakers (`risk_rules.py`):** We rely heavily on the automated streak breakers and daily loss limits. The VI.3 tripwire (rolling 30-trade PF) will kill the bot if performance degrades.
2. **Dynamic Daily Drawdown (`main_loop.py`):** Capped strictly at 6% of the current balance.
3. **No Averaging Down:** The bot strictly uses fixed SL/TP levels determined by ATR. 

## Sizing Ladder
Currently, the system uses a fixed `0.01` lot size (as defined in `main_loop.py` via `FIXED_LOT_SIZE`).
As the account balance grows:
- **Phase 1 ($100 - $800):** Maintain fixed 0.01 lots. Rely on high win-rate / high PF strategies (FVGNYTight PF 1.66) to build the buffer.
- **Phase 2 (>$800):** Transition to dynamic sizing (`calculate_dynamic_lot_size`) targeting a strict 1-2% risk per trade. At this balance, the 0.01 lot floor is no longer a constraint, and true percentage-based risk management takes over.
