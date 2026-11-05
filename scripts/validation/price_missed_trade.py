"""What would a missed signal have made? Priced on real minute bars.

Takes a signal the replay found, builds the stop and target the live bot would
have built (its ATR multiples on closed 15-minute bars), then walks forward
minute by minute to the first touch, applying the engine's costs. Read-only.

    python -I scripts/validation/price_missed_trade.py --when 2026-11-03T07:15 --strategy ASIAN_RANGE_FILTERED_V6 --sell
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

VPP = 100.0          # account currency per 1.0 price unit per 1.0 lot
LOTS = 0.02
COMM = 3.50 * LOTS   # realistic_ecn commission, per side pair
SLIP = 0.020         # 20 points of stop slippage, as the engine assumes
SWAP_LONG_NIGHT = -0.5155


def wilder_atr(h, l, c, period=14):
    tr = np.empty_like(h)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr = np.full_like(tr, np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--when", required=True, help="fill time, UTC, e.g. 2026-11-03T07:15")
    ap.add_argument("--strategy", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--buy", action="store_true")
    g.add_argument("--sell", action="store_true")
    ap.add_argument("--symbol", default=os.environ.get("ULTRA_SYMBOL", "XAUUSDm"))
    args = ap.parse_args()

    import MetaTrader5 as mt5

    from src.strategies.portfolio_atlas import PORTFOLIO

    leg = next((c() for c in PORTFOLIO if c().name == args.strategy), None)
    if leg is None:
        print(f"no live leg named {args.strategy}")
        return 1
    is_buy = bool(args.buy)
    fill_ts = int(dt.datetime.fromisoformat(args.when).replace(tzinfo=dt.timezone.utc).timestamp())

    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        return 1
    try:
        a = dt.datetime.utcfromtimestamp(fill_ts).replace(tzinfo=dt.timezone.utc)
        # range requests force the download; from_pos would serve stale cache
        m15 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M15,
                                   a - dt.timedelta(days=10), a + dt.timedelta(days=1))
        m1 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M1,
                                  a - dt.timedelta(hours=2), a + dt.timedelta(days=7))
        if m15 is None or m1 is None or not len(m15) or not len(m1):
            print("the terminal could not supply bars for that window")
            return 1

        # the ATR the live bot would have used: closed 15-minute bars only
        t15 = m15["time"].astype(np.int64)
        closed = t15 < fill_ts - (fill_ts % 900)
        h, l, c = (m15[k].astype(float)[closed] for k in ("high", "low", "close"))
        atr = float(wilder_atr(h, l, c)[-1])

        t1 = m1["time"].astype(np.int64)
        i0 = int(np.searchsorted(t1, fill_ts, side="left"))
        spread = float(m1["spread"][i0]) * 0.001
        mid = float(m1["open"][i0])
        entry = mid + spread if is_buy else mid       # buys fill at the ask

        sl_d, tp_d = leg.sl_atr_mult * atr, leg.tp_atr_mult * atr
        sl = entry - sl_d if is_buy else entry + sl_d
        tp = entry + tp_d if is_buy else entry - tp_d

        print(f"{args.strategy}  {'BUY' if is_buy else 'SELL'} {LOTS} lots")
        print(f"  fill      {dt.datetime.utcfromtimestamp(fill_ts):%Y-%m-%d %H:%M} UTC "
              f"({(dt.datetime.utcfromtimestamp(fill_ts) + dt.timedelta(hours=5, minutes=30)):%H:%M} IST) "
              f"at {entry:,.3f}  (spread {spread * 1000:.0f} pt)")
        print(f"  ATR(14)   ${atr:,.2f} on closed 15-minute bars")
        print(f"  stop      {sl:,.3f}  ({leg.sl_atr_mult} x ATR = ${sl_d:,.2f} away)")
        print(f"  target    {tp:,.3f}  ({leg.tp_atr_mult} x ATR = ${tp_d:,.2f} away)")

        hi = m1["high"].astype(float)[i0:]
        lo = m1["low"].astype(float)[i0:]
        sp = np.where(m1["spread"][i0:] > 0, m1["spread"][i0:].astype(float), 260.0) * 0.001
        hit_sl = (lo <= sl) if is_buy else (hi + sp >= sl)
        hit_tp = (hi >= tp) if is_buy else (lo + sp <= tp)
        hit = hit_sl | hit_tp
        if not hit.any():
            k = len(hi) - 1
            px = float(m1["close"].astype(float)[i0 + k]) + (0.0 if is_buy else sp[k])
            why = "still open at the end of the data"
        else:
            k = int(np.argmax(hit))
            if hit_sl[k]:
                px, why = (sl - SLIP if is_buy else sl + SLIP), "STOPPED OUT"
            else:
                px, why = tp, "TARGET HIT"
        xt = int(t1[i0 + k])
        gross = (px - entry) * (1 if is_buy else -1) * LOTS * VPP
        nights = xt // 86400 - fill_ts // 86400
        swap = SWAP_LONG_NIGHT * nights if is_buy else 0.0
        net = gross - COMM + swap
        print(f"\n  {why} at {px:,.3f} on "
              f"{dt.datetime.utcfromtimestamp(xt):%Y-%m-%d %H:%M} UTC "
              f"({(xt - fill_ts) / 3600:.1f} h later)")
        print(f"  gross ${gross:+,.2f}   commission ${-COMM:,.2f}   swap ${swap:+,.2f}")
        print(f"  NET   ${net:+,.2f}")

        worst = (float(lo[: k + 1].min()) if is_buy else float(hi[: k + 1].max()))
        adverse = (entry - worst) if is_buy else (worst - entry)
        print(f"  worst it went against us before that: ${adverse:,.2f} "
              f"({adverse / atr:.2f} x ATR of the {leg.sl_atr_mult} x ATR stop)")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
