"""What is this broker, actually? Measured at startup, not assumed.

Six things about a broker change how this bot trades, and all six are currently
constants tuned to Exness demo XAUUSDm:

  * the gold symbol's name           ("XAUUSDm" here, "XAUUSD" / "GOLD" elsewhere)
  * its price decimals               MAX_SPREAD_POINTS = 350 means $0.35 only at 3 decimals
  * the server's clock               strategies gate sessions on `bar_time % 86400`,
                                     which is server time, not UTC
  * the contract terms               tick value, contract size, volume step
  * the cost of holding              swap per night, and its sign
  * what the account allows          leverage, currency, filling mode, stops level

On a new account -- the Atlas one, when it arrives -- every one of them can
differ, and a wrong assumption is silent: the bot keeps trading, at the wrong
session times or through a spread gate that is ten times too loose.

`probe()` reads all of it from the terminal. `compare()` checks it against
`config/broker_expected.json` and returns one line per difference that matters.
main_loop runs both at startup, logs the profile, writes it to
logs/broker_profile.json and alerts on any difference, so a changed broker
announces itself instead of being discovered in the trade history.

    python -m src.core.broker_probe            # print the profile and the diff
    python -m src.core.broker_probe --save      # also make it the expected profile
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import asdict, dataclass, field  # noqa: F401  (asdict re-exported for tests)
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

EXPECTED_PATH = os.path.join("config", "broker_expected.json")
PROFILE_PATH = os.path.join("logs", "broker_profile.json")

# Symbol names brokers use for spot gold, most specific first. Exness suffixes
# retail accounts with "m"; others use ".a", "_ecn", "#", or nothing.
GOLD_PATTERNS = ("XAUUSD", "GOLD", "XAUUSD.", "GOLDm")

# What the spread gate means in money. MAX_SPREAD_POINTS is in points, and a
# point is 10**-digits, so the same number means a different price at 2, 3 or 5
# decimals. The gate is expressed in dollars here and converted per broker.
MAX_SPREAD_USD = 0.35


@dataclass
class BrokerProfile:
    """One measurement of a broker, taken from the terminal."""

    probed_utc: str = ""
    server: str = ""
    login: int = 0
    currency: str = ""
    leverage: int = 0
    trade_allowed: bool = False
    margin_mode: str = ""

    symbol: str = ""
    digits: int = 0
    point: float = 0.0
    contract_size: float = 0.0
    tick_size: float = 0.0
    tick_value: float = 0.0
    volume_min: float = 0.0
    volume_max: float = 0.0
    volume_step: float = 0.0
    stops_level_points: int = 0
    filling_modes: List[str] = field(default_factory=list)

    spread_points: int = 0
    spread_usd: float = 0.0
    swap_long: float = 0.0
    swap_short: float = 0.0
    swap_mode: str = ""
    swap_rollover_3days: int = 0

    # Server clock. `offset_hours` is server time minus UTC: the number every
    # session gate in src/strategies silently assumes is zero.
    server_time_utc: str = ""
    clock_offset_hours: Optional[float] = None
    clock_source: str = ""

    max_spread_points_for_this_broker: int = 0
    gold_candidates: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, sort_keys=True)


# ---------------------------------------------------------------------------
# probing
# ---------------------------------------------------------------------------


def find_gold_symbols(mt5: Any) -> List[str]:
    """Every tradeable symbol that looks like spot gold, best guess first."""
    try:
        symbols = mt5.symbols_get() or []
    except Exception:                                     # pragma: no cover - terminal
        return []
    names = [s.name for s in symbols]
    hits = [n for n in names if any(p in n.upper() for p in ("XAU", "GOLD"))]
    # spot gold against the dollar first, then anything gold-ish; shortest name
    # first inside each group, because suffixed variants are the exotic ones
    usd = sorted((n for n in hits if "USD" in n.upper()), key=len)
    rest = sorted((n for n in hits if "USD" not in n.upper()), key=len)
    return usd + rest


def market_probably_open(now: Optional[dt.datetime] = None) -> bool:
    """Is gold quoting right now, judged in UTC? Deliberately conservative.

    Spot gold trades Sunday 22:00 UTC to Friday 21:00 UTC with an hour-long
    rollover break each evening. This answers True only in the clear middle of a
    session, because its only job is to say whether a live tick can be trusted.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    wd = now.weekday()                            # Monday 0 ... Sunday 6
    h = now.hour + now.minute / 60.0
    if wd == 5:                                   # Saturday
        return False
    if wd == 6:                                   # Sunday: evening open only
        return h >= 22.5
    if wd == 4 and h >= 20.5:                     # Friday close
        return False
    return not (20.5 < h < 22.5)                  # the daily rollover break


def _clock_offset(mt5: Any, symbol: str) -> tuple:
    """(server-time minus UTC in hours, how it was measured).

    The broker stamps bars and ticks in its own timezone. While the market is
    open the last tick's time is the server clock, so the offset is the gap to
    real UTC, rounded to the nearest half hour (no broker runs on a stranger
    offset). With the market shut there is no fresh tick, so this reports None
    rather than guessing from a stale one.
    """
    now = dt.datetime.now(dt.timezone.utc)
    if not market_probably_open(now):
        # With the market shut the newest tick is hours old, and a tick that is a
        # whole number of hours stale looks exactly like a different timezone.
        # Guessing then would be worse than saying nothing.
        return None, "market closed -- no live tick to measure the clock against"
    tick = None
    try:
        tick = mt5.symbol_info_tick(symbol)
    except Exception:                                     # pragma: no cover - terminal
        tick = None
    if tick is None or not getattr(tick, "time", 0):
        return None, "no tick available"

    # A tick stamped in server time looks, from UTC, like it arrived `offset`
    # hours in the future. Timezones sit on half hours, so the nearest half hour
    # is the offset and whatever is left over is how stale the tick is.
    raw = (float(tick.time) - now.timestamp()) / 3600.0
    offset = round(raw * 2) / 2
    if not -12.0 <= offset <= 14.0:
        return None, f"implausible clock offset {offset:+g}h from the newest tick"
    stale_sec = abs(raw - offset) * 3600.0
    if stale_sec > 600:
        return None, f"newest tick is {stale_sec / 60:.0f} min stale"
    return offset, f"last tick, {stale_sec:.0f}s old"


def probe(mt5: Any, symbol: Optional[str] = None) -> BrokerProfile:
    """Read everything that matters off the terminal. Never raises."""
    p = BrokerProfile(probed_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    acct = None
    try:
        acct = mt5.account_info()
    except Exception:                                     # pragma: no cover - terminal
        acct = None
    if acct is not None:
        p.server = str(getattr(acct, "server", ""))
        p.login = int(getattr(acct, "login", 0) or 0)
        p.currency = str(getattr(acct, "currency", ""))
        p.leverage = int(getattr(acct, "leverage", 0) or 0)
        p.trade_allowed = bool(getattr(acct, "trade_allowed", False))
        _mm = getattr(acct, "margin_mode", None)
        p.margin_mode = ({0: "netting", 1: "exchange", 2: "hedging"}.get(int(_mm), str(_mm))
                         if _mm is not None else "")

    p.gold_candidates = find_gold_symbols(mt5)
    if not p.gold_candidates:
        p.notes.append("no gold symbol found on this broker")
    chosen = symbol or os.environ.get("ULTRA_SYMBOL") or (p.gold_candidates[0] if p.gold_candidates else "")
    if chosen and chosen not in p.gold_candidates and p.gold_candidates:
        p.notes.append(f"configured symbol {chosen!r} is not among the broker's gold symbols "
                       f"{p.gold_candidates[:5]}")
    p.symbol = chosen
    if not chosen:
        return p

    info = None
    try:
        mt5.symbol_select(chosen, True)
        info = mt5.symbol_info(chosen)
    except Exception:                                     # pragma: no cover - terminal
        info = None
    if info is None:
        p.notes.append(f"symbol_info({chosen!r}) returned nothing")
        return p

    p.digits = int(getattr(info, "digits", 0) or 0)
    p.point = float(getattr(info, "point", 0.0) or 0.0)
    p.contract_size = float(getattr(info, "trade_contract_size", 0.0) or 0.0)
    p.tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    p.tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    p.volume_min = float(getattr(info, "volume_min", 0.0) or 0.0)
    p.volume_max = float(getattr(info, "volume_max", 0.0) or 0.0)
    p.volume_step = float(getattr(info, "volume_step", 0.0) or 0.0)
    p.stops_level_points = int(getattr(info, "trade_stops_level", 0) or 0)
    p.spread_points = int(getattr(info, "spread", 0) or 0)
    p.spread_usd = round(p.spread_points * p.point, 4) if p.point else 0.0
    p.swap_long = float(getattr(info, "swap_long", 0.0) or 0.0)
    p.swap_short = float(getattr(info, "swap_short", 0.0) or 0.0)
    p.swap_mode = str(getattr(info, "swap_mode", ""))
    p.swap_rollover_3days = int(getattr(info, "swap_rollover3days", 0) or 0)

    modes = []
    fm = int(getattr(info, "filling_mode", 0) or 0)
    for bit, name in ((1, "FOK"), (2, "IOC"), (4, "RETURN")):
        if fm & bit:
            modes.append(name)
    p.filling_modes = modes

    p.max_spread_points_for_this_broker = (
        int(round(MAX_SPREAD_USD / p.point)) if p.point else 0)

    off, how = _clock_offset(mt5, chosen)
    p.clock_offset_hours = off
    p.clock_source = how
    if off is not None:
        p.server_time_utc = (dt.datetime.now(dt.timezone.utc)
                             + dt.timedelta(hours=off)).strftime("%Y-%m-%d %H:%M:%S")
    return p


# ---------------------------------------------------------------------------
# comparing
# ---------------------------------------------------------------------------

# Fields where a difference changes what the bot does. Everything else (spread
# right now, the probe timestamp) moves constantly and is recorded, not checked.
CHECKED = (
    ("symbol", "the traded symbol"),
    ("digits", "price decimals -- the spread gate is in points, so this rescales it"),
    ("point", "point size"),
    ("contract_size", "contract size -- changes what a lot is worth"),
    ("tick_value", "tick value -- changes every P&L and the Atlas limits in dollars"),
    ("volume_min", "minimum lot"),
    ("volume_step", "lot step"),
    ("clock_offset_hours", "server clock vs UTC -- every session gate assumes this"),
    ("currency", "account currency"),
    ("leverage", "account leverage"),
    ("margin_mode", "netting vs hedging -- changes how positions combine"),
)


def load_expected(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    path = path or EXPECTED_PATH
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        log.warning("broker_expected.json unreadable: %s", exc)
        return None


def compare(profile: BrokerProfile, expected: Optional[Dict[str, Any]] = None) -> List[str]:
    """One line per difference that changes how the bot trades."""
    exp = expected if expected is not None else load_expected()
    if not exp:
        return ["no expected broker profile recorded yet "
                "(python -m src.core.broker_probe --save writes one)"]
    got = asdict(profile)
    out: List[str] = []
    for key, why in CHECKED:
        if key not in exp:
            continue
        a, b = got.get(key), exp.get(key)
        if isinstance(a, float) or isinstance(b, float):
            if a is None or b is None:
                same = a == b
            else:
                same = abs(float(a) - float(b)) <= 1e-9
        else:
            same = a == b
        if not same:
            # an unmeasurable clock (market closed) is not a change
            if key == "clock_offset_hours" and a is None:
                out.append(f"clock offset could not be measured ({profile.clock_source}); "
                           f"expected {b}")
                continue
            out.append(f"{key}: now {a!r}, expected {b!r} -- {why}")
    if profile.swap_long and exp.get("swap_long") is not None:
        if (profile.swap_long < 0) != (float(exp["swap_long"]) < 0):
            out.append(f"swap_long changed sign: now {profile.swap_long}, "
                       f"expected {exp['swap_long']} -- overnight longs now cost the opposite")
    return out


def spread_gate_points(profile: BrokerProfile, configured: int) -> int:
    """The spread gate in points for this broker, keeping its dollar meaning."""
    if profile.max_spread_points_for_this_broker and profile.digits:
        return profile.max_spread_points_for_this_broker
    return configured


def save_expected(profile: BrokerProfile, path: Optional[str] = None) -> None:
    path = path or EXPECTED_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    body = asdict(profile)
    body["_note"] = ("The broker this configuration was validated against. "
                     "src/core/broker_probe.py compares every startup to it. "
                     "Replace it deliberately, with a decision-log entry.")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=1, sort_keys=True)


def write_profile(profile: BrokerProfile, path: Optional[str] = None) -> None:
    path = path or PROFILE_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(profile.to_json())


def summary(profile: BrokerProfile) -> str:
    p = profile
    clock = (f"UTC{p.clock_offset_hours:+g}" if p.clock_offset_hours is not None
             else f"clock unknown ({p.clock_source})")
    return (f"{p.server or 'unknown server'} acct {p.login} {p.currency} 1:{p.leverage} "
            f"{p.margin_mode} | {p.symbol} {p.digits}dp point {p.point:g} "
            f"lot {p.volume_min:g}-{p.volume_max:g} step {p.volume_step:g} "
            f"contract {p.contract_size:g} tick ${p.tick_value:g} | "
            f"spread {p.spread_points}pt (${p.spread_usd:g}) | swap {p.swap_long:g}/{p.swap_short:g} "
            f"| {clock} | spread gate {p.max_spread_points_for_this_broker}pt")


def startup_check(mt5: Any, symbol: Optional[str] = None) -> tuple:
    """Probe, record, compare. Returns (profile, differences). Never raises."""
    try:
        profile = probe(mt5, symbol)
    except Exception as exc:                              # pragma: no cover - terminal
        log.warning("broker probe failed: %s", exc)
        return None, [f"broker probe failed: {exc}"]
    try:
        write_profile(profile)
    except Exception as exc:                              # pragma: no cover - disk
        log.warning("could not write %s: %s", PROFILE_PATH, exc)
    return profile, compare(profile)


def main() -> int:                                        # pragma: no cover - CLI
    import argparse

    import MetaTrader5 as mt5

    ap = argparse.ArgumentParser(description="Measure this broker and compare it to the expected one.")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--save", action="store_true", help="make this the expected profile")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        return 1
    try:
        p = probe(mt5, args.symbol)
    finally:
        mt5.shutdown()

    print(summary(p))
    if p.gold_candidates:
        print(f"gold symbols on this broker: {', '.join(p.gold_candidates[:8])}")
    for n in p.notes:
        print(f"note: {n}")
    diffs = compare(p)
    print()
    if diffs:
        print("differences from the expected broker:")
        for d in diffs:
            print(f"  - {d}")
    else:
        print("matches the expected broker profile.")
    write_profile(p)
    print(f"\nwritten to {PROFILE_PATH}")
    if args.save:
        save_expected(p)
        print(f"recorded as the expected profile in {EXPECTED_PATH}")
    return 0


if __name__ == "__main__":                                # pragma: no cover - CLI
    raise SystemExit(main())
