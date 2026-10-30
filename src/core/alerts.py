"""Notification channel -- REAL_MONEY_READINESS.md IV.1.

The watchdog's `_alert()` has been a `print()` stub since it was written, which
means every failure it was built to catch (main_loop dying, hung heartbeat,
repeated restarts) announced itself only to a terminal nobody was watching.
The Sept 3-5 outage is the proof: main_loop, watchdog and protect_profit all
stopped, and nothing told anyone for two days.

Channels are opt-in via environment variables, so nothing here leaks config or
breaks if unconfigured:

    ULTRA_ALERT_TELEGRAM_TOKEN   + ULTRA_ALERT_TELEGRAM_CHAT   (Telegram bot)
    ULTRA_ALERT_WEBHOOK          (any POST-accepting URL: ntfy, Slack, Discord)

With neither set, alerts still land in logs/alerts.log and on stdout, so the
record exists even when delivery isn't configured. Every send is best-effort
and never raises -- an alerting failure must not take down trading.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence
import time as _time

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except ImportError:
    pass

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALERT_LOG = os.path.join(_ROOT, "logs", "alerts.log")
TIMEOUT = 15

# Priorities (owner 2026-10-30: "everything shouldn't be a warning").
#   INFO      silent push: status, heartbeat pulse, self-healed restarts, reports
#   TRADE     normal push: a trade opened or closed
#   WARN      normal push: something degraded; usually self-heals, worth a look
#   CRITICAL  normal push: trading has stopped or needs the owner to act now
INFO, TRADE, WARN, CRITICAL = "INFO", "TRADE", "WARN", "CRITICAL"


@dataclass(frozen=True)
class Level:
    icon: str
    silent: bool          # Telegram disable_notification


LEVELS = {
    INFO: Level("ℹ️", True),
    TRADE: Level("", False),
    WARN: Level("⚠️", False),
    CRITICAL: Level("🚨", False),
}


@dataclass(frozen=True)
class Alert:
    """One phone message: a bold headline, a few short lines, and (for problems) what to do."""
    headline: str
    lines: Sequence[str] = ()
    severity: str = INFO
    action: Optional[str] = None
    icon: Optional[str] = None      # overrides the level icon (trade messages use their own)

    def html(self) -> str:
        icon = self.icon if self.icon is not None else LEVELS.get(self.severity, LEVELS[WARN]).icon
        head = f"{icon} <b>{html.escape(self.headline)}</b>".strip()
        body = [html.escape(l) for l in self.lines if l]
        out = "\n".join([head] + body)
        if self.action:
            out += f"\n\n👉 {html.escape(self.action)}"
        return out


# Emoji/markers callers used to prepend by hand; the level icon replaces them.
_LEAD_MARKS = re.compile(r"^[\s⚠️🚨🛑ℹ️❌✅📊]+|[\s⚠️🛑]+$")


def _record(line: str) -> None:
    try:
        os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _alerts_disabled() -> bool:
    """True if running in a test suite or if explicitly suppressed via env var."""
    return bool("PYTEST_CURRENT_TEST" in os.environ or os.environ.get("ULTRA_DISABLE_ALERTS") == "1")


def _telegram(text: str, parse_html: bool = False, silent: bool = False) -> bool:
    if _alerts_disabled():
        return False
    token = os.environ.get("ULTRA_ALERT_TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("ULTRA_ALERT_TELEGRAM_CHAT") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    fields = {"chat_id": chat, "text": text}
    if parse_html:
        fields["parse_mode"] = "HTML"
    if silent:
        fields["disable_notification"] = "true"
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return bool(200 <= getattr(r, 'status', 500) < 300)
        except (urllib.error.URLError, OSError, ValueError) as e:
            if attempt == 0:
                _time.sleep(1.0)
                continue
            log.warning(f"telegram alert failed: {e}")
            return False


def _webhook(text: str, severity: str) -> bool:
    if _alerts_disabled():
        return False
    url = os.environ.get("ULTRA_ALERT_WEBHOOK")
    if not url:
        return False
    try:
        payload = json.dumps({"text": text, "severity": severity}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return bool(200 <= getattr(r, 'status', 500) < 300)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.warning(f"webhook alert failed: {e}")
        return False


def ist_stamp(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(IST)).astimezone(IST).strftime("%d %b %I:%M %p IST")


def send(message: str, severity: str = WARN, context: Optional[dict] = None,
         action: Optional[str] = None) -> bool:
    """Plain-text alert: first line is the headline, later lines and `context` are details."""
    if _alerts_disabled():
        return False
    lines = [l.strip() for l in re.sub(r"<[^>]+>", "", message).splitlines() if l.strip()]
    headline = _LEAD_MARKS.sub("", lines[0]) if lines else ""
    details = [l[:160] for l in lines[1:6]]
    details += [f"{k.replace('_', ' ').capitalize()}: {str(v)[:120]}"
                for k, v in (context or {}).items() if k != "source"]
    return notify(Alert(headline, tuple(details), severity, action))


def notify(alert: Alert) -> bool:
    return send_html(alert.html(), alert.severity)


def send_html(text: str, severity: str = TRADE) -> bool:
    """Message already formatted as Telegram HTML."""
    if _alerts_disabled():
        return False
    plain = html.unescape(re.sub(r"<[^>]+>", "", text))
    _record(f"[{severity}] " + plain.replace("\n", " | "))
    try:
        print(plain)
    except UnicodeEncodeError:
        print(plain.encode('ascii', 'replace').decode('ascii'))
    silent = LEVELS.get(severity, LEVELS[WARN]).silent
    delivered = False
    for fn in (lambda: _telegram(text, parse_html=True, silent=silent), lambda: _webhook(plain, severity)):
        try:
            delivered = fn() or delivered
        except Exception as e:
            log.warning(f"alert channel raised: {e}")
    return delivered


def record_only(message: str, severity: str = INFO) -> None:
    _record(f"[{severity}] {message}")


def configured() -> bool:
    return bool(os.environ.get("ULTRA_ALERT_TELEGRAM_TOKEN")
                or os.environ.get("ULTRA_ALERT_WEBHOOK"))
