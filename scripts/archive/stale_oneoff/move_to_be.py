import MetaTrader5 as _mt5
from typing import Any

mt5: Any = _mt5

def main():
    if not mt5.initialize():
        print("Init failed")
        return
        
    positions = mt5.positions_get(symbol="XAUUSDm")
    if not positions:
        print("No positions")
        return
        
    for p in positions:
        if p.type == 1 and p.sl > p.price_open:  # SELL and SL is above entry
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": p.ticket,
                "symbol": p.symbol,
                "sl": p.price_open,
                "tp": p.tp
            }
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Ticket {p.ticket}: SL moved to break-even ({p.price_open})")
            else:
                print(f"Ticket {p.ticket}: Failed to move SL. Result: {res}")
                
    mt5.shutdown()

if __name__ == "__main__":
    main()
