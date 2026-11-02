"""Why did nothing trade today? Replay every candle through the real strategies.

Read-only. Connects to the MT5 terminal on this machine, pulls the same bars
`main_loop` hands strategies, and walks today's closed 15-minute candles one at a
time, calling each live strategy's own `evaluate()` with exactly the view it
would have had at that moment (`rates[-1]` forming, `rates[-2]` just closed).

It then says, per candle, what each leg returned, and for the candles that are a
leg's entry slot it prints the numbers the decision turned on, so "no signal" is
a readable answer rather than a shrug. The daily trend gate is evaluated the same
way `main_loop` does.

    python -I scripts/validation/replay_today.py            # today
    python -I scripts/validation/replay_today.py --days 5    # the last 5 sessions

No orders are placed and nothing is written. The terminal is shut down on exit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SYMBOL = os.environ.get("ULTRA_SYMBOL", "XAUUSDm")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def ema(x, period):
    out = np.full(len(x), np.nan, dtype=float)
    if len(x) >= period:
        k = 2.0 / (period + 1.0)
        out[period - 1] = np.mean(x[:period])
        for i in range(period, len(x)):
            out[i] = (x[i] - out[i - 1]) * k + out[i - 1]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=1, help="how many recent sessions to replay")
    ap.add_argument("--symbol", default=SYMBOL)
    args = ap.parse_args()

    import MetaTrader5 as mt5

    from src.core import broker_probe
    from src.strategies.portfolio_atlas import PORTFOLIO

    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        print("Open the MetaTrader 5 terminal on this machine and try again.")
        return 1
    try:
        acct = mt5.account_info()
        mt5.symbol_select(args.symbol, True)
        info = mt5.symbol_info(args.symbol)
        if info is None:
            print(f"symbol_info({args.symbol!r}) returned nothing")
            return 1

        now_utc = dt.datetime.now(dt.timezone.utc)
        print(f"terminal : {getattr(acct, 'server', '?')}  account {getattr(acct, 'login', '?')} "
              f"({'demo' if getattr(acct, 'trade_mode', 0) == 0 else 'LIVE'})  "
              f"balance ${getattr(acct, 'balance', 0):,.2f}  equity ${getattr(acct, 'equity', 0):,.2f}")
        print(f"symbol   : {args.symbol}  {info.digits}dp  spread {info.spread}pt  "
              f"bid {info.bid:.3f} / ask {info.ask:.3f}")
        print(f"clock    : now {now_utc:%Y-%m-%d %H:%M} UTC = {now_utc.astimezone(IST):%H:%M} IST")

        # --- wait for the terminal to finish syncing ------------------------
        # A freshly initialised terminal serves cached history and downloads the
        # rest in the background. On 2026-11-02 the first call here returned bars
        # ending 11 hours earlier while ticks were live, and this script happily
        # reported "not one signal today" from them -- missing a signal that had
        # fired. Never conclude anything from bars that are not current.
        m15 = None
        for attempt in range(12):
            m15 = mt5.copy_rates_from_pos(args.symbol, mt5.TIMEFRAME_M15, 0, 2000)
            age = (dt.datetime.now(dt.timezone.utc).timestamp()
                   - float(m15[-1]["time"])) if m15 is not None and len(m15) else None
            if age is not None and age <= 25 * 60:
                break
            if not broker_probe.market_probably_open():
                print(f"market is closed; newest bar is "
                      f"{'unknown' if age is None else f'{age / 3600:.1f}h'} old, "
                      f"which is expected -- replaying what the terminal has")
                break
            print(f"terminal still syncing (newest bar "
                  f"{'missing' if age is None else f'{age / 60:.0f} min old'}), waiting... "
                  f"[{attempt + 1}/12]")
            time.sleep(5)
        else:
            print("the terminal never caught up. Open an XAUUSDm M15 chart in MT5 so it "
                  "downloads history, then run this again.")
            return 1
        if m15 is None or len(m15) < 300:
            print("not enough M15 history in the terminal")
            return 1
        forming = int(m15["time"][-1])
        bar_age = now_utc.timestamp() - forming
        # the forming bar opened at or before now; the gap to the current
        # quarter-hour in UTC is the server offset, to the nearest half hour --
        # but only while the bar is current. A stale bar gives a nonsense offset
        # (it read UTC-11 on 2026-11-02), so fall back to the broker's measured
        # clock instead of printing a fiction.
        if bar_age <= 25 * 60:
            offset_h = round((forming - int(now_utc.timestamp()) // 900 * 900) / 3600 * 2) / 2
            clock_note = "from the newest bar"
        else:
            offset_h = 0.0
            clock_note = (f"newest bar is {bar_age / 3600:.1f}h old, so the clock could not be "
                          f"measured -- times below assume UTC, which this broker uses "
                          f"(verified: weekly boundaries fall on Fri 20:45 / Sun 22:00)")
        probe_off, probe_src = broker_probe._clock_offset(mt5, args.symbol)
        print(f"server   : newest 15-min bar {dt.datetime.utcfromtimestamp(forming):%Y-%m-%d %H:%M} "
              f"({bar_age / 60:.0f} min old) -> clock UTC{offset_h:+g} {clock_note}")
        print(f"           tick: {'UTC%+g' % probe_off if probe_off is not None else 'unmeasurable'} "
              f"({probe_src})")

        def srv(ts):
            """A server-stamped bar time, printed as server time and as IST."""
            s = dt.datetime.utcfromtimestamp(int(ts))
            real = s - dt.timedelta(hours=offset_h)
            return s.strftime("%H:%M"), real.replace(tzinfo=dt.timezone.utc).astimezone(IST).strftime("%H:%M")

        # --- the daily trend gate, exactly as main_loop computes it ---------
        d1 = mt5.copy_rates_from_pos(args.symbol, mt5.TIMEFRAME_D1, 0, 60)
        bias = None
        if d1 is not None and len(d1) >= 21:
            c = d1["close"].astype(float)
            e = ema(c, 20)
            if not np.isnan(e[-2]):
                bias = "BULLISH" if c[-2] > e[-2] else "BEARISH"
                print(f"D1 gate  : last closed daily close {c[-2]:,.2f} vs EMA20 {e[-2]:,.2f} "
                      f"-> {bias} (only {'BUYS' if bias == 'BULLISH' else 'SELLS'} allowed today)")
        if bias is None:
            print("D1 gate  : no bias could be computed -> the gate fails closed, nothing may enter")

        strategies = [c() for c in PORTFOLIO]
        slots = {}
        for s in strategies:
            # every leg gates on the closed bar's server-second-of-day
            slots[s.name] = getattr(s, "_entry_sec", None)

        # --- replay --------------------------------------------------------
        t = m15["time"].astype(np.int64)
        days = sorted({int(x) // 86400 for x in t})[-args.days:]
        print()
        total_signals = 0
        for day in days:
            idx = [i for i in range(250, len(t) - 1) if t[i] // 86400 == day]
            if not idx:
                continue
            d = dt.datetime.utcfromtimestamp(day * 86400)
            print(f"=== {d:%A %Y-%m-%d} (server day) " + "=" * 30)
            fired = []
            for i in idx:
                view = m15[: i + 2]                     # [-2] = bar i, [-1] = forming
                stamp, ist = srv(t[i])
                hits = []
                for s in strategies:
                    try:
                        sig = s.evaluate(view, None)
                    except Exception as exc:
                        hits.append(f"{s.name} ERROR {exc}")
                        continue
                    if sig is not None:
                        allowed = not ((sig.is_buy and bias == "BEARISH")
                                       or (not sig.is_buy and bias == "BULLISH")
                                       or bias is None)
                        hits.append(f"{s.name} {'BUY' if sig.is_buy else 'SELL'}"
                                    f"{'' if allowed else ' -- BLOCKED by the D1 gate'}")
                        total_signals += 1
                if hits:
                    fired.append((stamp, ist, hits))
                    for h in hits:
                        print(f"  {stamp} server / {ist} IST   {h}")
            if not fired:
                print(f"  {len(idx)} closed candles, not one signal from any of the four legs")

            # why the Asian legs said nothing: print the numbers they looked at
            asia = [i for i in idx if t[i] % 86400 == 25200]
            if asia:
                i = asia[0]
                stamp, ist = srv(t[i])
                day_mask = (t // 86400 == day) & (t % 86400 < 21600)
                if day_mask.sum() >= 10:
                    hi = float(m15["high"][day_mask].max())
                    lo = float(m15["low"][day_mask].min())
                    w = hi - lo
                    mid = (hi + lo) / 2
                    close = float(m15["close"][i])
                    pct = w / mid
                    arf = next(s for s in strategies if s.name == "ASIAN_RANGE_FILTERED_V6")
                    reasons = []
                    if w < arf.min_range_abs:
                        reasons.append(f"range ${w:.2f} is under the ${arf.min_range_abs:.0f} floor")
                    if pct < arf.min_range_pct:
                        reasons.append(f"range {pct:.3%} is under the {arf.min_range_pct:.1%} minimum (dead day)")
                    if pct > arf.max_range_pct:
                        reasons.append(f"range {pct:.3%} is over the {arf.max_range_pct:.1%} maximum (wild day)")
                    if not reasons and lo <= close <= hi:
                        reasons.append(f"close {close:,.2f} finished INSIDE the range "
                                       f"({lo:,.2f}-{hi:,.2f}) -- no breakout")
                    print(f"  the {stamp} server / {ist} IST slot (Asian legs): range {lo:,.2f}-{hi:,.2f} "
                          f"= ${w:.2f} ({pct:.3%}), close {close:,.2f}")
                    for r in reasons:
                        print(f"     no entry: {r}")
                else:
                    print(f"  the Asian slot had only {int(day_mask.sum())} range candles (needs 10)")
            else:
                print("  the Asian entry slot (07:00 server) has not closed yet today")
            print()

        # --- what is open, and what closed today ---------------------------
        pos = mt5.positions_get(symbol=args.symbol) or []
        print(f"open positions on {args.symbol}: {len(pos)}")
        for p in pos:
            print(f"  #{p.ticket} magic {p.magic} {'BUY' if p.type == 0 else 'SELL'} {p.volume} "
                  f"@ {p.price_open:.3f}  now {p.price_current:.3f}  P&L ${p.profit + p.swap:,.2f}")
        frm = int((now_utc - dt.timedelta(days=1)).timestamp())
        deals = mt5.history_deals_get(frm, int(now_utc.timestamp())) or []
        closed = [d for d in deals if d.symbol == args.symbol and d.entry == 1]
        print(f"deals closed in the last 24h: {len(closed)}")
        for d in closed:
            print(f"  #{d.position_id} magic {d.magic} ${d.profit + d.swap + d.commission:,.2f} "
                  f"at {dt.datetime.utcfromtimestamp(d.time):%Y-%m-%d %H:%M} server")
        print(f"\nsignals found across the replay: {total_signals}")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
