"""Report the December demo EA's status and booked MT5 fills to Telegram."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import psutil
from dotenv import load_dotenv

from scripts.december_observer import END, START, SYMBOL
from scripts.demo_preflight import ReadOnlyTerminal
from src.core.alerts import Alert, CRITICAL, INFO, TRADE, WARN, ist_stamp, notify_telegram, telegram_chat_accessible


STRATEGIES = {7320: "Asian Range Filtered", 7324: "London Momentum Tight"}
EA_STATUS = "UltraCore_December2026_status.csv"
ATTEMPT_EVENTS = "UltraCore_AccessNov21_26_attempts.csv"
BREACHES = {
    "daily_loss_breach": "Daily equity loss limit",
    "trailing_equity_breach": "Trailing equity loss limit",
    "inactivity_breach": "30-day inactivity limit",
}
STATES = {
    "waiting_for_start": (INFO, "Waiting for the scheduled start"),
    "awaiting_market": (INFO, "Evaluation started. Waiting for the XAUUSD market to open."),
    "active": (INFO, "Evaluation active"),
    "evaluation_passed": (INFO, "Evaluation target reached. New entries stopped."),
    "window_complete": (INFO, "Evaluation entry window closed"),
    "after_window": (INFO, "Evaluation entry window closed"),
    "daily_loss_breach": (CRITICAL, "Daily equity loss limit breached"),
    "trailing_equity_breach": (CRITICAL, "Trailing equity loss limit breached"),
    "inactivity_breach": (CRITICAL, "30-day inactivity limit breached"),
    "midnight_equity_unverified": (CRITICAL, "Midnight equity unverified. Entries blocked."),
    "pending_orders_refused": (CRITICAL, "Unexpected pending orders. Entries blocked."),
    "foreign_position_refused": (CRITICAL, "Unexpected position. Entries blocked."),
    "restart_reconciliation_required": (CRITICAL, "EA restarted. Account reconciliation required."),
    "initial_account_state_unverified": (CRITICAL, "Evaluation start could not be verified. Entries blocked."),
    "run_identity_persistence_failed": (CRITICAL, "EA run identity could not be saved. Entries blocked."),
    "exposure_during_connection_loss": (CRITICAL, "Connection lost with exposure. Entries blocked."),
    "account_identity_refused": (CRITICAL, "Expected demo account could not be verified"),
    "terminal_unavailable": (WARN, "MT5 terminal unavailable"),
    "ea_status_unavailable": (WARN, "EA status missing or stale"),
    "ea_start_unconfirmed": (WARN, "EA start has not been confirmed"),
    "trade_permission_disabled": (WARN, "MT5 automated trading permission is off"),
    "deal_history_unavailable": (WARN, "MT5 deal history unavailable"),
}


def write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_ea_status(terminal, now):
    path = Path(terminal.commondata_path) / "Files" / EA_STATUS
    try:
        lines = path.read_text(encoding="ascii").splitlines()
        stamp, state, balance, peak, anchor, count, *rest = next(csv.reader(lines))
        wrote_at = datetime.strptime(stamp, "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if state in STATES and -5 <= (now - wrote_at).total_seconds() <= 120:
            return state, (balance, peak, anchor, count, *rest)
    except (OSError, ValueError, StopIteration):
        pass
    return "ea_status_unavailable", None


def read_attempt_events(terminal):
    path = Path(terminal.commondata_path) / "Files" / ATTEMPT_EVENTS
    try:
        with path.open(encoding="ascii", newline="") as stream:
            return [row for row in csv.reader(stream) if len(row) == 8]
    except (OSError, UnicodeError):
        return []


def snapshot(api, now, login, server):
    terminal, account = api.terminal_info(), api.account_info()
    if not terminal or not terminal.connected or not account:
        return "terminal_unavailable", None, [], []
    if (account.trade_mode, account.login, account.server) != (0, login, server):
        return "account_identity_refused", None, [], []
    state, stats = read_ea_status(terminal, now)
    ts = int(now.timestamp())
    if ts < START:
        return state, stats, [], []
    deals = api.history_deals_get(START, ts + 1)
    if state in {"waiting_for_start", "awaiting_market", "active"}:
        if ts >= END:
            state = "after_window"
        elif state == "waiting_for_start" and ts >= START + 120:
            state = "ea_start_unconfirmed"
        elif not (terminal.trade_allowed and account.trade_allowed and account.trade_expert):
            state = "trade_permission_disabled"
        elif deals is None:
            state = "deal_history_unavailable"
    return state, stats, deals or [], read_attempt_events(terminal)


def fill_alert(strategy, side, action, lots, price, cash, detail):
    return Alert(f"XAUUSD demo · {action}",
                 (f"XAUUSD · {strategy}", f"{side} position · {lots:.2f} lots · fill {price:.3f}",
                  f"Cash impact of this fill {cash:+.2f} USD", detail), TRADE)


def fill_messages(deals):
    """Include only positions opened by the two December strategies."""
    ordered = sorted(
        (d for d in deals if d.symbol == SYMBOL and d.time_msc >= START * 1000 and d.type in (0, 1)),
        key=lambda d: (d.time_msc, d.ticket),
    )
    entries = {d.position_id: d for d in reversed(ordered)
               if d.entry == 0 and d.magic in STRATEGIES and d.time_msc < END * 1000}
    for d in ordered:
        entry = entries.get(d.position_id)
        if entry is None or d.entry not in (0, 1, 3):
            continue
        if d.entry == 0 and d.magic != entry.magic:
            continue
        side = "Buy" if entry.type == 0 else "Sell"
        action = "Entry filled" if d.entry == 0 else "Exit filled"
        cash = d.profit + d.commission + d.swap + d.fee
        stamp = ist_stamp(datetime.fromtimestamp(d.time_msc / 1000, tz=timezone.utc))
        yield str(d.ticket), fill_alert(STRATEGIES[entry.magic], side, action, d.volume,
                                        d.price, cash, f"{stamp} · MT5 deal #{d.ticket}")


def status_alert(state, stats, now):
    severity, title = STATES[state]
    lines = [title, ist_stamp(now)]
    if stats:
        balance, peak, anchor, count, *attempt = stats
        if attempt:
            lines.append(f"Evaluation attempt #{attempt[0]}")
        lines.extend((f"Virtual balance ${balance} · target $5,150.00",
                      f"Equity peak ${peak} · UTC daily anchor ${anchor} · open positions {count}"))
    if state == "evaluation_passed":
        lines.append("Funded and payout checks are separate.")
    if state == "awaiting_market":
        lines.append("Demo evaluation runs 21 Nov through 15 Dec 2026 IST.")
    if state in BREACHES:
        lines.append("New entries stopped. A fresh demo attempt requires a flat, verified account.")
    return Alert("XAUUSD demo · Atlas Access", lines, severity)


def attempt_alert(row):
    stamp, number, event, balance, equity, floor, count, _ = row
    date = ist_stamp(datetime.fromtimestamp(int(stamp), timezone.utc))
    if event == "retry_started":
        return Alert("XAUUSD demo · Fresh evaluation started",
                     (f"Attempt #{number} · virtual balance ${balance} · target $5,150.00",
                      "Previous breach remains recorded. Demo positions and pending orders are clear.",
                      date), TRADE)
    if event in BREACHES:
        lines = [f"Attempt #{number} failed · {BREACHES[event]}",
                 f"Balance ${balance} · equity ${equity} · open positions {count}", date]
        if float(floor) > 0:
            lines.insert(2, f"Equity floor ${floor}")
        lines.append("New entries stopped. A fresh attempt starts when the demo is flat and verified, within the test window.")
        return Alert("XAUUSD demo · Evaluation account breached", lines, CRITICAL)
    return None


def format_samples(now):
    stamp = ist_stamp(now)
    stats = ("5000.00", "5000.00", "5000.00", "0", "1")
    events = [
        (str(int(now.timestamp())), "1", "daily_loss_breach", "4780.00", "4740.00", "4750.00", "1", "0"),
        (str(int(now.timestamp())), "2", "retry_started", "5000.00", "5000.00", "0.00", "0", "0"),
    ]
    samples = [status_alert("awaiting_market", stats, now),
               fill_alert("Asian Range Filtered", "Buy", "Entry filled", .02, 3540.250, -.10, stamp),
               fill_alert("Asian Range Filtered", "Buy", "Exit filled", .02, 3552.250, 23.90, stamp),
               *(attempt_alert(row) for row in events),
               status_alert("evaluation_passed", ("5150.00", "5150.00", "5000.00", "0", "2"), now),
               status_alert("trade_permission_disabled", None, now),
               status_alert("window_complete", stats, now)]
    lines = []
    for sample in samples:
        lines.extend((sample.headline, *sample.lines, ""))
    return Alert("TEST ONLY · XAUUSD demo message formats",
                 ("Sample values. No trade, breach or reset occurred.", "", *lines), TRADE)


def report(state, stats, deals, now, ledger, ledger_path, send=notify_telegram, events=()):
    if now.timestamp() < START:
        return True
    logged = ledger.setdefault("attempt_events", [])
    for row in events:
        key = ":".join(row[:3])
        message = attempt_alert(row)
        if message is None or key in logged:
            continue
        if not send(message):
            return False
        logged.append(key)
        write_json(ledger_path, ledger)
    for ticket, message in fill_messages(deals):
        if ticket in ledger["fills"]:
            continue
        if not send(message):
            return False
        ledger["fills"].append(ticket)
        write_json(ledger_path, ledger)
    if state == ledger["state"]:
        return True
    journal_breach = state in BREACHES and stats and len(stats) == 5 and any(
        row[1] == stats[4] and row[2] == state for row in events
    )
    if not journal_breach and not send(status_alert(state, stats, now)):
        return False
    ledger["state"] = state
    write_json(ledger_path, ledger)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--probe", action="store_true", help="Check Telegram access without sending")
    action.add_argument("--send-format-test", action="store_true", help="Post one clearly labeled format sample")
    parser.add_argument("--terminal", type=Path)
    parser.add_argument("--expected-login", type=int)
    parser.add_argument("--expected-server")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(args.settings)
    if args.probe:
        accessible = telegram_chat_accessible()
        print("TELEGRAM_CHAT_ACCESSIBLE=" + str(accessible).lower())
        return 0 if accessible else 1
    if args.send_format_test:
        delivered = notify_telegram(format_samples(datetime.now(timezone.utc)))
        print("TELEGRAM_FORMAT_TEST_ACCEPTED=" + str(delivered).lower())
        return 0 if delivered else 1
    if not all((args.terminal, args.expected_login, args.expected_server, args.output)):
        parser.error("MT5 path, pinned demo identity and output are required")
    import MetaTrader5 as mt5

    app = args.terminal.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output / "telegram-delivered.json"
    ledger = (json.loads(ledger_path.read_text(encoding="utf-8"))
              if ledger_path.exists() else {"state": None, "fills": []})
    status_path = args.output / "telegram-status.json"
    api = ReadOnlyTerminal(mt5)
    try:
        while True:
            now = datetime.now(timezone.utc)
            running = any(proc.info["exe"] and Path(proc.info["exe"]) == app
                          for proc in psutil.process_iter(["exe"], ad_value=""))
            if running and api.initialize(str(app), timeout=5000):
                try:
                    state, stats, deals, events = snapshot(api, now, args.expected_login, args.expected_server)
                finally:
                    api.shutdown()
            else:
                state, stats, deals, events = "terminal_unavailable", None, [], []
            healthy = report(state, stats, deals, now, ledger, ledger_path, events=events)
            write_json(status_path, {"timestamp": now.isoformat(), "ea_state": state,
                                    "last_alert": ledger["state"], "fills_reported": len(ledger["fills"]),
                                    "send_failed": not healthy})
            time.sleep(30)
    finally:
        api.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
