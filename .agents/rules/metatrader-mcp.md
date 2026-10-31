# MetaTrader MCP Troubleshooting

> **Note:** the live bot (`src.core.main_loop`) executes through the
> **`MetaTrader5` Python package directly**, not through MCP. MCP is used only
> for ad-hoc queries. Execution failures in
> the bot show up in `logs/main_loop.log`, not as MCP errors — but the error
> codes below are the same.

When diagnosing MetaTrader trade execution failures, check these in order:

1. **Error 10027 (AutoTrading disabled by client):** The Algo Trading button in MT5 toolbar is turned off. User must re-enable it. Note: It auto-disables when switching accounts if "Disable algorithmic trading when the account has been changed" is checked in Tools > Options > Expert Advisors.

2. **Error 10017 (Trade disabled):** The account is connected with an **Investor Password** (read-only). Check `account_info()` — if `trade_allowed: False` but `trade_expert: True`, the password needs to be changed to the **Master Password** in `mcp_config.json`.

3. **Error 10018 (Market closed):** This is normal behavior — the market is closed (weekends for Forex/Gold). Forex markets: Mon 00:00 – Fri 23:59 GMT.

4. **Error 10014 (Invalid volume):** The lot size is outside the symbol's allowed range. Check the symbol's minimum volume (Gold is typically 0.01 lots; some stock CFDs require 1.0+).

5. **Symbol not found:** The broker server may not support that symbol. MetaQuotes-Demo only has basic Forex pairs and some stocks. For XAUUSD, crypto, or indices, the user needs a real broker demo account (Exness, IC Markets, Pepperstone, etc.).

## Exness Symbol Naming Convention

Exness Standard accounts append a lowercase "m" suffix to all symbols:
- Gold: **XAUUSDm** (not XAUUSD)
- 24/7 Gold: **XAUUSD247m**
- Euro: **EURUSDm**
- Bitcoin vs Gold: **BTCXAUm**

Always use the "m" suffix when placing trades on Exness Standard accounts.
