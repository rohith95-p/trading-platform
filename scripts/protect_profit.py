"""Profit protection for open positions on the demo bot.

Owner's rule (2026-09-03): if a trade is in profit but NOT reaching target and a
clean reversal shows up, book the profit rather than ride it to the stop.

Watches every open XAUUSDm position. On each new M15 close, for a position that
is currently GREEN, closes it if either:
  A. clean reversal against it -- last M15 candle is a strong opposite-direction
     bar (body > 55% of range) that closes through the prior bar's extreme, OR
     price closed back through the M15 EMA20 against the position.
  B. giveback -- peak favourable excursion was >= $4 and current P/L has fallen
     back below $1.5 (a decent winner is turning into a scratch).

Runs alongside main_loop. Does NOT touch losing positions -- their fixed stop
handles those. Ctrl-C to stop.

    python -m scripts.protect_profit
"""
import json
import os
import time
import sys
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core import scope  # noqa: E402  (magic allowlist; fail closed if unreadable)

IST = timezone(timedelta(hours=5, minutes=30))
_LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
COOLDOWN_FILE = os.path.join(_LOGS, "cooldown.json")
POSITIONS_FILE = os.path.join(_LOGS, "positions.txt")
SYMBOL = "XAUUSDm"
POLL = 20
GIVEBACK_PEAK = 6.0   # only protect once peak profit >= $6
GIVEBACK_FLOOR = 1.0  # close if profit falls back below $1 (was $1.5 -- too tight)
MIN_GREEN = 0.5      # only act when at least this much in profit
COOLDOWN_MIN = 45    # after a reversal close, block that leg from re-entering
OWN_MAGICS = scope.load_own_magics()


def _set_cooldown(leg_name):
    """Tell main_loop not to re-enter this leg for COOLDOWN_MIN minutes."""
    try:
        try:
            cd = json.load(open(COOLDOWN_FILE))
        except (OSError, ValueError):
            cd = {}
        cd[leg_name] = time.time() + COOLDOWN_MIN * 60
        json.dump(cd, open(COOLDOWN_FILE, "w"))
    except OSError:
        pass


def _ist():
    return datetime.now(IST).strftime("%H:%M:%S IST")


def ema(a, n):
    k = 2 / (n + 1)
    e = np.full(len(a), np.nan)
    if len(a) >= n:
        e[n - 1] = a[:n].mean()
        for i in range(n, len(a)):
            e[i] = a[i] * k + e[i - 1] * (1 - k)
    return e


def clean_reversal_against(is_buy, r):
    """r = recent M15 rates. True if the last CLOSED bar is a clean reversal
    against a long (is_buy) / short."""
    o, h, l, c = r["open"], r["high"], r["low"], r["close"]
    j = -2  # last closed bar
    body = abs(c[j] - o[j])
    rng = max(h[j] - l[j], 1e-9)
    strong = body / rng > 0.55
    e20 = ema(c, 20)
    if is_buy:
        bar_bear = c[j] < o[j] and strong and c[j] < l[j - 1]
        lost_ema = c[j] < e20[j] and c[j - 1] >= e20[j - 1]
        return bar_bear or lost_ema
    else:
        bar_bull = c[j] > o[j] and strong and c[j] > h[j - 1]
        lost_ema = c[j] > e20[j] and c[j - 1] <= e20[j - 1]
        return bar_bull or lost_ema


def close_position(p, reason):
    tick = mt5.symbol_info_tick(SYMBOL)
    price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
    req = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": p.volume,
        "type": mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": p.ticket, "price": price, "deviation": 30,
        "magic": p.magic, "comment": "protect_profit", "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    ok = res and res.retcode == mt5.TRADE_RETCODE_DONE
    print(f"[{_ist()}] {'CLOSED' if ok else 'CLOSE FAILED'} #{p.ticket} "
          f"P/L {p.profit:+.2f} -- {reason}"
          + ("" if ok else f" ({res.comment if res else 'no reply'})"))
    if ok:
        _set_cooldown(p.comment)
        print(f"[{_ist()}]   -> {p.comment} on {COOLDOWN_MIN}min re-entry cooldown")
    return ok


def main():
    if not mt5.initialize():
        print("MT5 init failed"); return
    print(f"[{_ist()}] profit-protection watcher started (managing magics {sorted(OWN_MAGICS)} only).")
    peak = {}          # ticket -> peak profit seen
    last_bar = None
    while True:
        try:
            all_ps = [p for p in (mt5.positions_get(symbol=SYMBOL) or [])]
            # Manage ONLY Ultra Core's own positions; another system's trades are shown in the status file but never touched.
            ps = [p for p in all_ps if p.magic in OWN_MAGICS]
            acc = mt5.account_info()
            # status file so other tools can read state without their own MT5 connection
            try:
                tick = mt5.symbol_info_tick(SYMBOL)
                t_info = mt5.terminal_info()
                r_check = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 5)
                last_candle_str = datetime.fromtimestamp(int(r_check["time"][-2]), tz=IST).strftime("%H:%M") if r_check is not None and len(r_check) >= 2 else "NONE"
                conn_status = t_info.connected if t_info else False
                bid_str = f"{tick.bid:.2f}" if tick else "NONE"
                lines = [f"{_ist()}  bal {acc.balance:.2f}  eq {acc.equity:.2f}  open {len(ps)} (foreign {len(all_ps) - len(ps)})  bid {bid_str}  last_M15 {last_candle_str}  conn {conn_status}"]
                for p in all_ps:
                    d = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    tag = "" if p.magic in OWN_MAGICS else " FOREIGN(magic %s)" % p.magic
                    lines.append(f"  #{p.ticket} {d} {p.volume} @ {p.price_open:.2f} "
                                 f"now {p.price_current:.2f} SL {p.sl:.2f} TP {p.tp:.2f} "
                                 f"P/L {p.profit:+.2f} [{p.comment}]{tag}")
                if all_ps:
                    lines.append(f"  combined(all) {sum(p.profit for p in all_ps):+.2f}")
                open(POSITIONS_FILE, "w").write("\n".join(lines) + "\n")
            except Exception as e:
                open(POSITIONS_FILE, "w").write(f"ERROR in status: {e}\n")
            if not ps:
                peak.clear()
            r = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 40)
            bar_t = int(r["time"][-2]) if r is not None else None
            new_bar = bar_t is not None and bar_t != last_bar

            for p in ps:
                peak[p.ticket] = max(peak.get(p.ticket, p.profit), p.profit)
                if p.profit < MIN_GREEN:
                    continue
                is_buy = p.type == mt5.ORDER_TYPE_BUY
                # A. giveback
                if peak[p.ticket] >= GIVEBACK_PEAK and p.profit <= GIVEBACK_FLOOR:
                    close_position(p, f"giveback (peak +{peak[p.ticket]:.2f} -> +{p.profit:.2f})")
                    continue
                # B. clean reversal, only checked on a fresh M15 close
                if new_bar and r is not None and clean_reversal_against(is_buy, r):
                    close_position(p, "clean M15 reversal, banking profit")

            if new_bar:
                last_bar = bar_t
        except Exception as e:
            print(f"[{_ist()}] error: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
