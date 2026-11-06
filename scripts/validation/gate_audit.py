"""Why would a trade be refused right now? Every gate, in order, with its verdict.

Between a strategy's signal and an order at the broker there are fifteen places
that can say no. Each one logs its own reason, but only in the bot's log on the
machine it runs on -- so "no trades today" has taken a candle replay and an
account cross-check to explain, three times running, and each time a different
gate turned out to be the one saying no.

This asks every gate directly, in the order `_execute_signal` asks them, and
prints what each would answer for a hypothetical entry right now. Run it on the
machine the bot runs on. Read-only: it places nothing.

    python -I scripts/validation/gate_audit.py
    python -I scripts/validation/gate_audit.py --buy      # test a long instead
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except ImportError:
    pass

OK, NO, NA = "ok", "WOULD REFUSE", "n/a"


def line(n, name, verdict, detail=""):
    mark = {OK: "  ok ", NO: " STOP", NA: "  -- "}[verdict]
    print(f"{mark} {n:>2}. {name:<34s} {detail}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--buy", action="store_true", help="test a long (default: short)")
    ap.add_argument("--symbol", default=os.environ.get("ULTRA_SYMBOL", "XAUUSDm"))
    args = ap.parse_args()
    is_buy = args.buy

    import MetaTrader5 as mt5

    from src.core import market_hours, news_filter, ops, risk_rules, scope
    from src.core import risk_manager as rm
    from src.core import validation_ledger
    from src.strategies.portfolio_atlas import PORTFOLIO

    now = dt.datetime.now(dt.timezone.utc)
    ist = now + dt.timedelta(hours=5, minutes=30)
    print(f"gate audit {now:%Y-%m-%d %H:%M} UTC / {ist:%H:%M} IST   "
          f"testing a {'BUY' if is_buy else 'SELL'} on {args.symbol}\n")

    refusals = []

    def check(n, name, refuse, detail=""):
        line(n, name, NO if refuse else OK, detail)
        if refuse:
            refusals.append(name)

    # ---- 0. before the loop even gets to a signal -----------------------
    halt = ops.halt_status()
    check(0, "halt latch", halt is not None,
          f"{halt.get('reason') if halt else 'clear'}")
    check(1, "STOP kill-switch file", os.path.exists("STOP"),
          "present -- bot flattens and stops" if os.path.exists("STOP") else "absent")
    check(2, "measurement-only mode", ops.measure_only(),
          "ULTRA_MEASURE_ONLY is set" if ops.measure_only() else "off")

    rep = validation_ledger.check_live_config()
    allow_unval = os.environ.get("ULTRA_ALLOW_UNVALIDATED") == "1"
    check(3, "config matches a backtest", not rep["validated"] and not allow_unval,
          f"fingerprint {rep['fingerprint']}, validated={rep['validated']}"
          + (", bypassed by ULTRA_ALLOW_UNVALIDATED" if allow_unval else ""))

    if not mt5.initialize():
        line(4, "MT5 connection", NO, f"initialize() failed: {mt5.last_error()}")
        return 1
    try:
        ti, acct = mt5.terminal_info(), mt5.account_info()
        check(4, "MT5 connected + algo on",
              not (ti and ti.connected and ti.trade_allowed),
              f"connected={getattr(ti, 'connected', None)} algo={getattr(ti, 'trade_allowed', None)}")

        m15 = mt5.copy_rates_from_pos(args.symbol, mt5.TIMEFRAME_M15, 0, 250)
        bar_age = (now.timestamp() - float(m15[-1]["time"])) if m15 is not None and len(m15) else None
        check(5, "candle feed is current", bar_age is None or bar_age > 25 * 60,
              "no bars" if bar_age is None else f"newest bar {bar_age / 60:.0f} min old")

        d1 = mt5.copy_rates_from_pos(args.symbol, mt5.TIMEFRAME_D1, 0, 60)
        bias = None
        if d1 is not None and len(d1) >= 21:
            from src.core.order_flow import compute_d1_bias
            bias = compute_d1_bias(d1)
        check(6, "daily trend gate has a bias", bias is None,
              f"{bias or 'NONE -- fails closed, nothing may enter'}")
        if bias:
            wrong = (is_buy and bias == "BEARISH") or (not is_buy and bias == "BULLISH")
            check(7, f"daily gate allows a {'buy' if is_buy else 'sell'}", wrong,
                  f"bias {bias}")
        else:
            line(7, "daily gate direction", NA)

        mh_ok, mh_why = market_hours.allow_new_entry(ist.replace(tzinfo=None))
        check(8, "market hours / trading window", not mh_ok, mh_why or "open")

        nf_blocked, nf_why = news_filter.is_near_news_event(ist.replace(tzinfo=None))
        check(9, "own news filter", nf_blocked, nf_why or "clear")

        info = mt5.symbol_info(args.symbol)
        spread = int(getattr(info, "spread", 0) or 0)
        check(10, "spread gate", spread > rm.MAX_SPREAD_POINTS,
              f"{spread} pt against a {rm.MAX_SPREAD_POINTS} pt cap")

        foreign = []
        if scope.block_on_foreign_enabled():
            own = scope.load_own_magics()
            foreign = [p for p in (mt5.positions_get(symbol=args.symbol) or [])
                       if p.magic not in own]
        check(11, "no foreign positions", bool(foreign), f"{len(foreign)} found")

        pos = mt5.positions_get(symbol=args.symbol) or []
        from src.core import execution_handler as eh
        check(12, "position / volume caps",
              len(pos) >= eh.MAX_CONCURRENT_POSITIONS
              or sum(p.volume for p in pos) >= (eh.MAX_TOTAL_VOLUME or 9e9),
              f"{len(pos)}/{eh.MAX_CONCURRENT_POSITIONS} open, "
              f"{sum(p.volume for p in pos):.2f}/{eh.MAX_TOTAL_VOLUME} lots")

        if acct is not None:
            dec, _st = risk_rules.evaluate(balance=acct.balance, equity=acct.equity,
                                           margin_used=getattr(acct, "margin", 0.0) or 0.0)
            check(13, "risk rulebook", risk_rules.ENFORCE and not dec.allow_new_entries,
                  f"{dec.reason or 'clear'}"
                  + ("" if risk_rules.ENFORCE else " (shadow mode, not enforced)"))

        # ---- the Atlas rule engine, gate by gate -------------------------
        from src.atlas import AccountInfo, AtlasState, OrderRequest, load_rules
        from src.atlas.mcp_monitor import AtlasMCPMonitor
        from src.atlas.rules import AtlasRuleEngine

        eng = AtlasRuleEngine(load_rules(
            allow_unverified=["daily_loss_eod_computation", "ea_approval_required"]))
        phase = os.environ.get("ULTRA_ATLAS_PHASE", "evaluation")
        mon = AtlasMCPMonitor(poll_interval=300.0)
        events = mon.force_refresh().news_events or []
        print(f"\n   Atlas phase {phase}; news calendar has {len(events)} event(s)")
        for ev in events[:5]:
            print(f"     {ev}")
        news_reason = eng.news_block_reason(now, events)
        check(14, "Atlas news window", news_reason is not None,
              news_reason or "clear")
        if news_reason and "unreadable" in news_reason:
            print("        ^ this is OUR feed, not the market: it refuses EVERY trade "
                  "while it lasts")

        if acct is not None:
            ai = AccountInfo(balance=float(acct.balance), equity=float(acct.equity),
                             margin=float(getattr(acct, "margin", 0.0) or 0.0),
                             free_margin=float(getattr(acct, "margin_free", 0.0) or 0.0),
                             ts_utc=now,
                             floating_pnl=float(getattr(acct, "profit", 0.0) or 0.0))
            st = AtlasState.new(initial_balance=5000.0, now_utc=now, phase=phase,
                                equity=ai.equity)
            leg = PORTFOLIO[0]()
            atr = 8.0
            order = OrderRequest(symbol=args.symbol,
                                 stop_risk_usd=float(eh.FIXED_LOT_SIZE * 100.0 * atr
                                                     * (leg.sl_atr_mult or 2.0)),
                                 margin_required=float(eh.FIXED_LOT_SIZE
                                                       * float(info.ask) * 100.0 / 50.0),
                                 volume=eh.FIXED_LOT_SIZE,
                                 side="buy" if is_buy else "sell")
            d = eng.check_order(order, ai, st, now, events)
            check(15, "Atlas rule engine, whole order", not d.allow,
                  ", ".join(str(r) for r in d.reasons) or "allowed")
    finally:
        mt5.shutdown()

    print()
    if refusals:
        print(f"RESULT: {len(refusals)} gate(s) would refuse a trade right now:")
        for r in refusals:
            print(f"   - {r}")
    else:
        print("RESULT: every gate is open. A signal right now would become an order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
