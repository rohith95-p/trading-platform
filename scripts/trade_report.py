"""Read-only report of today's trades straight from MT5 history and the bot log (never sends an order).

    venv\\Scripts\\python.exe scripts\\trade_report.py            # today (IST)
    venv\\Scripts\\python.exe scripts\\trade_report.py 2026-10-30 # a given IST day
"""
import datetime as dt
import os
import sys

import MetaTrader5 as m

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UTC = dt.timezone.utc
SYMBOL = "XAUUSDm"
NAMES = {7310: "Donchian Trend", 7320: "Asian Range Filtered", 7311: "Asian Breakout",
         7324: "London Momentum Tight", 7313: "NY Session Reversal"}
REASON = {0: "closed by hand", 1: "closed by hand (phone)", 2: "closed by hand (web)", 3: "closed by the bot",
          4: "STOP LOSS hit", 5: "TAKE PROFIT hit", 6: "stop-out"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ist(ts):
    return dt.datetime.fromtimestamp(ts, UTC).astimezone(IST).strftime("%H:%M:%S")


def main():
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.datetime.now(IST).date()
    d0 = dt.datetime.combine(day, dt.time(0), IST)
    d1 = d0 + dt.timedelta(days=1)
    if not m.initialize():
        print("MT5 not reachable"); return
    acct = m.account_info()
    # epoch seconds, not tz-aware datetimes: the MT5 API mis-reads aware datetimes and returns nothing
    deals = [d for d in (m.history_deals_get(int(d0.timestamp()) - 3 * 86400, int(d1.timestamp()) + 86400) or [])
             if d.symbol == SYMBOL]
    by_pos = {}
    for d in deals:
        by_pos.setdefault(d.position_id, []).append(d)
    rows = []
    for pid, ds in by_pos.items():
        ins = [d for d in ds if d.entry == 0]
        outs = [d for d in ds if d.entry in (1, 2)]
        if not ins or not outs or not (d0.timestamp() <= outs[-1].time < d1.timestamp()):
            continue
        rows.append((ins[0], outs[-1], ds))
    rows.sort(key=lambda r: r[0].time)

    print(f"=== {day:%a %d %b %Y} | account {acct.login} | balance ${acct.balance:,.2f} | equity ${acct.equity:,.2f}")
    total = 0.0
    spans = []
    for i, (a, b, ds) in enumerate(rows, 1):
        buy = a.type == 0
        orders = m.history_orders_get(position=a.position_id) or []
        sl = next((o.sl for o in orders if o.sl), 0.0)
        tp = next((o.tp for o in orders if o.tp), 0.0)
        pl = sum(d.profit for d in ds)
        comm = sum(d.commission for d in ds)
        swap = sum(d.swap for d in ds)
        net = pl + comm + swap
        total += net
        vol = a.volume
        risk = abs(a.price - sl) * vol * 100 if sl else 0.0
        reward = abs(tp - a.price) * vol * 100 if tp else 0.0
        bars = m.copy_rates_range(SYMBOL, m.TIMEFRAME_M1, a.time - 60, b.time + 60)
        if bars is not None:
            bars = bars[(bars["time"] >= a.time // 60 * 60) & (bars["time"] <= b.time)]
        if bars is not None and len(bars):
            best = (bars["high"].max() - a.price) if buy else (a.price - bars["low"].min())
            worst = (a.price - bars["low"].min()) if buy else (bars["high"].max() - a.price)
            mfe, mae = best * vol * 100, worst * vol * 100
        else:
            mfe = mae = float("nan")
        mins = (b.time - a.time) / 60
        spans.append((a.time, b.time))
        print(f"\n--- Trade {i}: {NAMES.get(a.magic, a.magic)} (magic {a.magic}, ticket {a.position_id})")
        print(f"  Direction  : {'BUY' if buy else 'SELL'} {vol:.2f} lot")
        print(f"  Entry      : {a.price:.2f} at {ist(a.time)} IST")
        print(f"  Stop/Target: {sl:.2f} / {tp:.2f}  (risk ${risk:.2f}, reward ${reward:.2f}, "
              f"R:R 1:{reward / risk if risk else 0:.1f})")
        print(f"  Exit       : {b.price:.2f} at {ist(b.time)} IST -> {REASON.get(b.reason, b.reason)}")
        print(f"  Held       : {int(mins // 60)}h {int(mins % 60)}m")
        print(f"  Best/worst while open: +${mfe:.2f} / -${mae:.2f}")
        print(f"  Result     : profit ${pl:+.2f}, commission ${comm:+.2f}, swap ${swap:+.2f} => NET ${net:+.2f}"
              f" ({net / risk if risk else 0:+.2f} R)")
    print(f"\nDay total: {len(rows)} trades, NET ${total:+.2f}")
    overlap = any(s2 < e1 for (s1, e1), (s2, e2) in zip(spans, spans[1:]))
    print(f"Trades open at the same time: {'yes' if overlap else 'no (each closed before the next opened)'}")

    d = m.copy_rates_range(SYMBOL, m.TIMEFRAME_D1, int(d0.timestamp()) - 200 * 86400, int(d1.timestamp()))
    if d is not None and len(d) > 21:
        rng = d["high"] - d["low"]
        days = [dt.datetime.fromtimestamp(int(t), UTC).date() for t in d["time"]]
        k = next((j for j, x in enumerate(days) if x == day), len(d) - 1)
        fri = sorted([r for r, x in zip(rng[:k], days[:k]) if x.weekday() == 4][-12:])
        print(f"\nVolatility: {day:%a} range ${rng[k]:.2f} (high {d['high'][k]:.2f}, low {d['low'][k]:.2f}) | "
              f"avg of last 20 days ${rng[k - 20:k].mean():.2f} | median of last 12 Fridays ${fri[len(fri) // 2] if fri else 0:.2f}")
        print(f"Daily trend gate: close {d['close'][k - 1]:.2f} vs 20-day EMA -> see D1 GATE lines below")

    log = os.path.join(ROOT, "logs", "main_loop.log")
    if os.path.exists(log):
        keys = ("Lots:", "Highlander", "VETO", "BLOCKED", "D1 GATE", "ATLAS")
        want = day.isoformat()
        lines, gate_seen = [], set()
        with open(log, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.startswith(want) or not any(k in line for k in keys):
                    continue
                if "D1 GATE" in line:            # one per hour is enough
                    h = line[11:13] + line[20:22]
                    if h in gate_seen:
                        continue
                    gate_seen.add(h)
                lines.append(line.rstrip())
        print(f"\n--- Bot log, {want} (entries, blocks, trend gate hourly) ---")
        print("\n".join(lines[-60:]) or "(nothing)")
    m.shutdown()


if __name__ == "__main__":
    main()
