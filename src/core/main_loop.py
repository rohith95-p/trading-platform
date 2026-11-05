"""
main_loop.py -- Ultra Core v3 Final Boss Orchestrator.

PHILOSOPHY:
  - NEVER hardcode dollar limits. Everything scales with ATR.
  - Fixed lots, positions run to their fixed SL/TP -- no trailing, no pyramiding.
  - Atlas mode: portfolio_atlas (DonchianTrend, AsianRangeFiltered, AsianBreakout).
  - Non-Atlas: portfolio_v6 (DonchianTrend only).
  - Sessions in IST; D1 bias gate disabled for V6 strategies.

This file is the loop: startup() holds every check that can refuse the start,
and _run_guarded() is the scan. Whether a signal becomes an order, and what
happens to the position afterwards, is src/core/order_flow.py.

Resilience (src/core/resilience.py -- does not affect trading):
  - single-instance lockfile
  - kill switch: create a file named STOP in the project root -> flatten + halt
  - heartbeat file (logs/heartbeat), loop-state persistence (logs/loop_state.json)
  - startup safety check (right account, tradeable), MT5 auto-reconnect

Run:
    python -m src.core.main_loop
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except ImportError:
    pass
import time as _time
import logging
import json
import re
import MetaTrader5 as _mt5
from typing import Any, Optional
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

mt5: Any = _mt5

from src.core.data_fetcher import DataFetcher
from src.core import risk_manager as risk_manager_mod
from src.core import broker_probe  # measures the broker at startup (2026-11-01)
from src.core.risk_manager import RiskManager
from src.core.execution_handler import ExecutionHandler, FIXED_LOT_SIZE
from src.core import resilience
from src.core import trade_log
from src.core import risk_rules
from src.core import market_hours
from src.core import trade_alerts
from src.core import journal  # 23:59 IST trade journal + day summary (2026-10-30)
from src.core import news_filter  # III.5 -- blocks entries around tier-1 macro events
from src.core import ops  # halt latch, measurement-only mode, external heartbeat (2026-10-18)
from src.core import scope  # own-magic strategy view vs account-wide risk view (2026-10-18)
# MorningMomentum (grade H), EMAPullback (grade E), AsianSweep (grade E) were
# archived to src/strategies/archive/ on 2026-09-01 (rohith phase 3): all three
# scored below the random-entry control (HYP-020) and MorningMomentum's 83%
# claim was never reproducible (HYP-006). See docs/research/STRATEGY_REGISTRY.md.
# EMAStack (rohith phase 2, HYP-027) superseded 2026-09-01 by the 4-leg
# portfolio below -- kept in src/strategies/ema_stack.py for reference but
# no longer imported here.
# V5 portfolio retired — all 4 legs were net-negative (PF 0.73/0.86/0.98).
from src.strategies.portfolio_v6 import PORTFOLIO as PORTFOLIO_V6  # Donchian Trend V6 (replaces losing V5 legs)
from src.strategies.portfolio_atlas import PORTFOLIO as PORTFOLIO_ATLAS
from src.atlas import (
    AtlasRuleEngine, AtlasState, AccountInfo, load_rules, RulesError,
)
from src.atlas.mcp_monitor import AtlasMCPMonitor
from src.core import atlas_bridge
from src.core import live_status
# Names kept here so every caller, script and test that reads them off
# main_loop keeps working; the code itself lives in the two modules above.
from src.core.atlas_bridge import (                       # noqa: F401
    ATLAS_STATE_FILE, HALT_CLEAR_HELP, _atlas_account_info, _daily_only,
    _explain_atlas, _init_atlas, _load_atlas_state, _save_atlas_state,
)
from src.core.live_status import (                        # noqa: F401
    _alert_foreign_exposure, _push_ops_heartbeat, _write_status,
)
from src.core import order_flow
# _COOLDOWN_FILE and ENABLE_D1_GATE are deliberately NOT re-exported: they are
# plain values, so a re-export here is a copy, and patching the copy (a test
# pointing at main_loop) would leave order_flow reading the original. Patch and
# read them on order_flow. The names below are functions and mutable containers,
# where the re-export is the same object.
from src.core.order_flow import (                        # noqa: F401
    EXECUTED_ORDERS_DEDUP, _TRANSIENT_BLOCK, _calc_ema, _check_vi3_tripwire,
    _close_all_positions, _d1_bias_allows, _execute_signal, _leg_in_cooldown,
    _manage_open_positions, _override_may_apply, _record_closed_trades,
)

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))

# One alert per blind-feed episode, not one per scan.
_FEED_BLIND = {"alerted": False}

# ---------------------------------------------------------------------------
# Logging (IST timestamps)
# ---------------------------------------------------------------------------

class ISTFormatter(logging.Formatter):
    """Log formatter that outputs timestamps in IST."""
    def formatTime(self, record, datefmt=None):
        ct = datetime.fromtimestamp(record.created, tz=IST)
        if datefmt:
            return ct.strftime(datefmt)
        return ct.strftime("%Y-%m-%d %I:%M:%S %p IST")

handler = logging.StreamHandler()
handler.setFormatter(ISTFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SYMBOL = os.environ.get("ULTRA_SYMBOL", "XAUUSDm")
LOOP_INTERVAL = 60  # seconds between scans

# live_status writes the watchdog snapshot and the ops heartbeat, both of which
# need the terminal handle and the symbol this loop trades.
live_status.bind(mt5, SYMBOL)

# Atlas Funded integration: enable with ULTRA_ATLAS_MODE=1 (env var).
# When on, portfolio_atlas replaces portfolio_v6, the AtlasRuleEngine gates
# every order, and the MCP monitor polls account health in the background.
ATLAS_MODE = os.environ.get("ULTRA_ATLAS_MODE", "0") == "1"

# Unverified rules the engine must acknowledge to load (see atlas_access.json).
_ATLAS_ALLOW_UNVERIFIED = atlas_bridge.ALLOW_UNVERIFIED

# order_flow sends the orders, so it needs the same terminal handle, symbol and
# mode this loop runs on. Bound here, at import, before anything can call it.
order_flow.bind(mt5, SYMBOL, ATLAS_MODE)

_ATLAS_RT: dict = atlas_bridge.RUNTIME  # filled in by startup() when ATLAS_MODE is on

# ---------------------------------------------------------------------------
# Exit-management switches (rohith-2, 2026-09-03)
#
# Both were ON live and NEITHER was in the backtest that validated portfolio_v4.
# scripts/live_config_ab.py replayed the same 100 days with all four legs on one
# shared account and measured the difference:
#
#   2 pos, trail OFF, pyramid OFF  ->  PF 1.478   net +$843.43   maxDD 21.4%
#   2 pos, trail ON,  pyramid ON   ->  PF 0.592   net  -$93.59   maxDD 89.0%
#
# Trailing is the killer. It activates at 0.7*ATR and follows 0.3*ATR behind,
# so it exits around 0.4*ATR net -- but these legs target 2.25-4.0*ATR and live
# entirely on rare large winners. It lifts win rate (29.6% -> 52.9%) while
# collapsing profit factor, converting 2.5*ATR winners into 0.4*ATR ones.
# Live confirmation 2026-09-02 22:22: FVG #2 trailed out at +$4.70 with its
# target still $18 away.
#
# Pyramiding adds a second full-size position 0.5*ATR into a move -- a worse
# entry, more extended, with its own full stop -- so a reversal loses on both.
#
# Positions now run to their fixed SL/TP, exactly as validated.
# 2026-09-25 audit: this had been silently flipped to True by the 2026-09-24
# "repository cleanup" commit (b8ab85c), contradicting this comment, the
# module docstring, and REPO_GUIDE.md's explicit "if you see it True again,
# that's a regression" warning. Trailing was backtested net-negative
# (PF 0.592, -$93.59). Reverted to the documented/validated default.
ENABLE_TRAILING = False
ENABLE_PYRAMIDING = False
CLOSE_ONLY_TRAIL = True


def _ist_now() -> str:
    return datetime.now(IST).strftime("%I:%M:%S %p IST")


def run():
    """Main entry point."""

    # Single-instance guard -- refuse to start if another main_loop is alive.
    if not resilience.acquire_lock():
        return
    resilience.heartbeat()

    try:
        _run_guarded()
    finally:
        resilience.release_lock()


def startup():
    """Every check that has to pass before the first scan, then the modules the loop runs on.

    Returns the built modules, or None when a check refuses the start.

    The ORDER of these checks is not editorial. Each is here because of a
    specific incident -- named in the comment above it -- and several depend on
    an earlier one having run: the broker probe rescales the spread gate before
    any gate reads it, the config-integrity gate stamps ops.BUILD before the
    first heartbeat carries a fingerprint, and the hedging check runs before any
    position's magic is believed. Nothing here may be reordered.
    """
    if not mt5.initialize():
        log.error("MT5 initialisation failed. Exiting.")
        return None

    # Startup safety: right account, tradeable connection, symbol present.
    if not resilience.startup_safety_check(mt5, SYMBOL):
        log.error("Startup safety check FAILED. Not trading. Fix the above and restart.")
        return None

    # What broker is this, measured rather than assumed (2026-11-01). The symbol
    # name, its price decimals, the server's clock, the contract terms and the
    # swap all differ between brokers, and every one of them is baked into a
    # constant somewhere. On a new account (Atlas) a difference here is silent:
    # the bot keeps trading, at the wrong session times or through a spread gate
    # that means ten times what it should. So it is checked, logged and alerted.
    _bprofile, _bdiffs = broker_probe.startup_check(mt5, SYMBOL)
    if _bprofile is not None:
        log.info(f"BROKER: {broker_probe.summary(_bprofile)}")
        _gate = broker_probe.spread_gate_points(_bprofile, risk_manager_mod.MAX_SPREAD_POINTS)
        if _gate != risk_manager_mod.MAX_SPREAD_POINTS:
            log.warning(f"Spread gate rescaled for this broker: "
                        f"{risk_manager_mod.MAX_SPREAD_POINTS} -> {_gate} points "
                        f"(${broker_probe.MAX_SPREAD_USD} at {_bprofile.digits} decimals)")
            risk_manager_mod.MAX_SPREAD_POINTS = _gate
    if _bdiffs == [broker_probe.NO_EXPECTED]:
        log.warning(f"BROKER: {broker_probe.NO_EXPECTED}")      # first run, not a change
    elif _bdiffs:
        from src.core import alerts as _al
        _lines = ["Broker profile differs from the validated one:"]
        _lines += [f"- {d}" for d in _bdiffs]
        _al.send(os.linesep.join(_lines), severity=_al.WARN)
        for d in _bdiffs:
            log.warning(f"BROKER DIFFERENCE: {d}")

    # Persistent halt latch (2026-10-18): a halt survives crashes and restarts and is cleared only by a deliberate
    # operator action (python -m scripts.halt clear --note "...").
    _halt = ops.halt_status()
    if _halt is not None:
        from src.core import alerts
        msg = (f"START REFUSED: halt latch is set ({_halt.get('source')}: {_halt.get('reason')}). "
               f"Review, reconcile, then clear with: python -m scripts.halt clear --note \"...\"")
        log.error(msg)   # the watchdog sees the latch and tells the owner once; no alert per refused start
        return None
    if ops.measure_only():
        log.warning("MEASUREMENT-ONLY MODE (ULTRA_MEASURE_ONLY): scanning and logging, NO orders will be sent.")
    risk_rules.LIVE_CONTEXT = True   # lets risk_rules relax the monthly/peak hard halts, and only on a DEMO account
    _active_portfolio = PORTFOLIO_ATLAS if ATLAS_MODE else PORTFOLIO_V6
    try:
        _own = scope.load_own_magics()
        _missing = scope.check_portfolio_magics(_active_portfolio, _own)
    except scope.ScopeConfigError as e:
        log.error(f"START REFUSED: {e}")
        return None
    if _missing:
        log.error(f"START REFUSED: PORTFOLIO magics {_missing} are not in config/ultra_magics.json")
        return None
    if ATLAS_MODE:
        log.info("ATLAS MODE ENABLED — portfolio_atlas, Atlas rule engine and MCP monitor active.")

    # Config-integrity gate: refuse to trade a configuration nobody has run
    # through a backtest and recorded. This is the fix for a real recurring
    # failure -- exposure caps raised without re-validating, the D1 gate left
    # in a different state than any tested backtest, a strategy fix that
    # silently changed what an unrelated script tested. See
    # src/core/validation_ledger.py and RESEARCH_LEDGER.md HYP-047/048.
    from src.core import validation_ledger
    _cfg_report = validation_ledger.check_live_config()
    ops.BUILD["fingerprint"] = _cfg_report.get("fingerprint")
    if _cfg_report["validated"]:
        _res = _cfg_report["match"]["result"]
        log.info(f"CONFIG VALIDATED: fingerprint {_cfg_report['fingerprint']} matches "
                 f"{_cfg_report['match']['source']} ({_cfg_report['match']['recorded_at']}): {_res}")
    else:
        log.error(f"CONFIG NOT VALIDATED: live fingerprint {_cfg_report['fingerprint']} "
                  f"matches no recorded backtest.")
        for line in _cfg_report["diff"]:
            log.error(f"  differs from most recent recorded config: {line}")
        if os.environ.get("ULTRA_ALLOW_UNVALIDATED") != "1":
            log.error("Refusing to trade an unvalidated configuration. Re-run a backtest "
                       "and record it (validation_ledger.record), or set "
                       "ULTRA_ALLOW_UNVALIDATED=1 to override (not recommended).")
            return None
        log.warning("ULTRA_ALLOW_UNVALIDATED=1 set -- proceeding on an unvalidated config.")

    # --- Modules ---
    fetcher = DataFetcher(SYMBOL)
    # Netting accounts merge every system's deals into ONE position per symbol, so magic ownership of an open position
    # is ambiguous. The scoping model assumes HEDGING; refuse to trade otherwise (measurement-only just warns).
    _acct0 = mt5.account_info()
    _mm = getattr(_acct0, "margin_mode", None)
    if _mm is not None and _mm != 2:   # 0 retail netting, 1 exchange, 2 retail hedging
        _txt = f"account margin mode is {_mm} (not hedging): per-magic position ownership is unreliable."
        if ops.measure_only():
            log.warning(_txt)
        else:
            log.error(f"START REFUSED: {_txt}")
            return None
    if not ops.measure_only() and scope.block_on_foreign_enabled():
        _foreign0 = fetcher.get_foreign_exposure()
        if _foreign0:
            from src.core import alerts
            _msg = (f"START REFUSED: another system holds positions on {SYMBOL} while orders are enabled: "
                    f"{scope.foreign_report(_foreign0)}. Use measurement-only mode, a separate account, "
                    f"or close them manually.")
            log.error(_msg)
            alerts.send(f"Bot refused to start: other trades on {SYMBOL}", alerts.CRITICAL,
                        context={"found": scope.foreign_report(_foreign0)},
                        action="Close the other trades (or use a separate account), then restart the bot.")
            return None
    risk = RiskManager(SYMBOL)
    executor = ExecutionHandler(SYMBOL, risk_manager=risk)
    # rohith phase 3 (2026-09-01): portfolio_v4 replaces EMAStack alone.
    # Validated together (PF 1.512, $703 net/~100d) is not the same claim as
    # "EMAStack plus these 4" -- that 5-strategy combination was never tested,
    # so EMAStack is not run alongside them. See HYP-036/038.
    strategies = [cls() for cls in _active_portfolio]

    # Atlas rule engine + MCP monitor (only in ATLAS_MODE)
    atlas_engine: Optional[AtlasRuleEngine] = None
    atlas_state: Optional[AtlasState] = None
    atlas_monitor: Optional[AtlasMCPMonitor] = None
    if ATLAS_MODE:
        try:
            _acct_init = mt5.account_info()
            atlas_engine, atlas_state, atlas_monitor = _init_atlas(
                float(_acct_init.balance), float(_acct_init.equity))
            _ATLAS_RT.update(engine=atlas_engine, state=atlas_state, monitor=atlas_monitor)
            log.info(f"ATLAS: rule engine loaded (phase={atlas_state.phase}, "
                     f"balance=${atlas_state.initial_balance:.2f}, "
                     f"trailing DD floor=${atlas_engine.trailing_floor(atlas_state):.2f})")
        except RulesError as e:
            log.error(f"ATLAS: rule engine failed to load: {e}")
            log.error("Cannot trade in Atlas mode without the rule engine. Exiting.")
            return None
        except Exception as e:
            log.error(f"ATLAS: unexpected init error: {e}")
            return None

    return SimpleNamespace(fetcher=fetcher, risk=risk, executor=executor,
                           strategies=strategies, atlas_engine=atlas_engine,
                           atlas_state=atlas_state, atlas_monitor=atlas_monitor)


def _run_guarded():
    """The scan loop. startup() has already refused anything that should stop it."""
    _mods = startup()
    if _mods is None:
        return
    fetcher, risk, executor = _mods.fetcher, _mods.risk, _mods.executor
    strategies = _mods.strategies
    atlas_engine, atlas_state = _mods.atlas_engine, _mods.atlas_state

    # Daily drawdown shutdown flag
    drawdown_shutdown = False
    shutdown_date = None

    # CRIT-1 / P0-3: Dedup mechanisms to ensure signals never re-fire on the same candle.
    # Record the candle each strategy last acted on and refuse to act on it twice.
    last_fired_candle: dict = {s.name: None for s in strategies}

    # Restore loop state so a restart mid-candle can't re-fire a signal.
    _saved = resilience.load_state()
    if _saved.get("last_fired_candle"):
        for name, candle in _saved["last_fired_candle"].items():
            if name in last_fired_candle:
                last_fired_candle[name] = candle
    if risk_rules.daily_cap_relaxed():
        log.warning("DAILY LOSS CAP RELAXED (demo account, owner decision 2026-10-22): no daily drawdown shutdown.")
    elif _saved.get("drawdown_shutdown") and _saved.get("shutdown_date") == str(datetime.now(IST).date()):
        drawdown_shutdown = True
        shutdown_date = datetime.now(IST).date()
        log.info("STATE: daily drawdown shutdown restored for today.")

    # P0-3: Restore (magic, bar_time, direction) dedup keys from trade log & state file
    executed_orders_dedup = trade_log.load_order_dedup_keys()
    if _saved.get("executed_dedup_keys"):
        for item in _saved["executed_dedup_keys"]:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                try:
                    executed_orders_dedup.add((int(item[0]), int(item[1]), str(item[2]).upper()))
                except (ValueError, TypeError):
                    pass
    EXECUTED_ORDERS_DEDUP.clear()
    EXECUTED_ORDERS_DEDUP.update(executed_orders_dedup)
    log.info(f"DEDUP: Initialized {len(executed_orders_dedup)} executed order dedup keys.")

    mt5_fail_count = 0

    # Positions seen on the previous loop -- None until the first pass, so
    # positions already open at startup are adopted, not counted as closes.
    known_position_tickets = None

    log.info("=" * 60)
    log.info("Ultra Core v3 -- Final Boss Engine")
    log.info(f"Symbol: {SYMBOL}")
    log.info(f"Active Strategies: {[s.name for s in strategies]}")
    from src.core.execution_handler import MAX_CONCURRENT_POSITIONS as _mcp, MAX_TOTAL_VOLUME as _mtv
    log.info(f"Lots: FIXED {FIXED_LOT_SIZE} | Max exposure: {_mtv} | Max positions: {_mcp}")
    log.info(f"Daily loss cap: 6% of balance | Session: IST-adaptive")
    log.info(f"Trailing: {'ON' if ENABLE_TRAILING else 'OFF'} | "
             f"Pyramiding: {'ON' if ENABLE_PYRAMIDING else 'OFF'} | "
             f"D1 gate: {'ON' if order_flow.ENABLE_D1_GATE else 'OFF'}")
    log.info(f"Resilience: lock={resilience.LOCK_FILE} | kill switch=create '{resilience.STOP_FILE}'")
    log.info(f"Atlas mode: {'ON' if ATLAS_MODE else 'OFF'}"
             + (f" (phase={atlas_state.phase})" if atlas_state else ""))
    log.info(f"News filter: {'ENABLED' if news_filter.ENABLE_NEWS_FILTER else 'DISABLED'} "
             f"(±{news_filter.NEWS_BLACKOUT_MINUTES}min blackout around tier-1 events)")
    news_filter.invalidate_cache()  # ensure calendar is freshly loaded at startup
    _upcoming = news_filter.upcoming_events(hours_ahead=8.0)
    if _upcoming:
        log.info("Upcoming tier-1 events (next 8h):")
        for _ev in _upcoming:
            log.info(f"  {_ev['minutes_away']:>4}min: {_ev['name']} @ {_ev['utc_time']} UTC ({_ev['date']})")
    log.info("=" * 60)
    print(f"\n[{_ist_now()}] >>> Ultra Core v3 is LIVE.\n")

    current_date = datetime.now(IST).date()

    while True:
        try:
            now_ist = datetime.now(IST)
            
            # ----------------------------------------------------------
            # Midnight IST tasks
            # ----------------------------------------------------------
            if current_date != now_ist.date():
                log.info("Midnight IST transition detected.")
                current_date = now_ist.date()
            journal.maybe_run(mt5, now_ist)   # 23:59 IST: record the day's trades + day summary (replaces the midnight report)
            resilience.heartbeat()
            _push_ops_heartbeat(fetcher, drawdown_shutdown)  # external dead-man heartbeat (status payload)
            _write_status(fetcher)
            try:
                _alert_foreign_exposure(fetcher.get_foreign_exposure())
            except Exception as _e:
                log.debug(f"foreign-exposure check skipped: {_e}")
            resilience.save_state(last_fired_candle, drawdown_shutdown, shutdown_date,
                                  executed_dedup_keys=[list(k) for k in executed_orders_dedup])

            # Feed closed-trade results to the risk_rules streak breakers. Runs
            # every loop -- a stop can fill while the bot is in drawdown_shutdown.
            known_position_tickets = _record_closed_trades(fetcher, known_position_tickets)

            # ----------------------------------------------------------
            # Kill switch: STOP file in the project root -> flatten + halt
            # ----------------------------------------------------------
            if resilience.kill_switch_active():
                log.warning("KILL SWITCH ACTIVE (STOP file present). Flattening and halting.")
                print(f"[{_ist_now()}] KILL SWITCH -- closing all positions, halting.")
                _close_all_positions(fetcher, executor, "STOP file")
                break

            # ----------------------------------------------------------
            # Friday Kill Switch: Flatten for the weekend
            # ----------------------------------------------------------
            if market_hours.should_flatten_for_weekend(now_ist):
                open_pos = fetcher.get_own_positions()
                if open_pos:
                    log.warning("FRIDAY KILL SWITCH: Market closing soon. Flattening all positions.")
                    print(f"[{_ist_now()}] FRIDAY KILL SWITCH -- flattening for the weekend.")
                    _close_all_positions(fetcher, executor, "Friday close before the weekend", "INFO")
                # Sleep and skip the rest of the loop until market reopens
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Reset drawdown shutdown at midnight IST
            # ----------------------------------------------------------
            if drawdown_shutdown and shutdown_date != now_ist.date():
                drawdown_shutdown = False
                shutdown_date = None
                log.info("Midnight IST -- drawdown reset. Trading resumes.")
                print(f"[{_ist_now()}] RESET: New day, drawdown cleared.")

            if drawdown_shutdown:
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Fetch data early so the blind-session counter is always
            # updated, even when a spread or news gate fires.
            # ----------------------------------------------------------
            risk.refresh_macro_rules()
            m15_rates = fetcher.get_m15_rates(250)
            m5_rates = fetcher.get_m5_rates(100)

            conn_ok, conn_reason = resilience.check_connection_and_freshness(mt5, m15_rates)
            if conn_ok and _FEED_BLIND["alerted"]:
                _FEED_BLIND["alerted"] = False
                from src.core import alerts as _fa
                _fa.send("Prices are back: the bot can see the market again", _fa.WARN)
            got_data = conn_ok and m15_rates is not None and len(m15_rates) >= 200
            mt5_fail_count = resilience.note_fetch_result(mt5, got_data, mt5_fail_count, reason=conn_reason)
            if not got_data:
                if not conn_ok:
                    log.warning(f"LIVENESS CHECK FAILED: {conn_reason}. Skipping signal evaluation.")
                    # 2026-11-04: a blind feed used to be a log line and nothing
                    # more for eight minutes, while the process, the heartbeat and
                    # the MT5 connection all looked healthy. A tradeable signal
                    # was missed that way. Tell the owner on the first scan, once
                    # per episode, because "scanning but blind" is not visible
                    # from anywhere else.
                    if not _FEED_BLIND["alerted"]:
                        _FEED_BLIND["alerted"] = True
                        from src.core import alerts as _fa
                        _fa.send("Bot is scanning but cannot see prices: no trades will be taken",
                                 _fa.CRITICAL, context={"reason": conn_reason},
                                 action=("Open an XAUUSDm M15 chart in MT5 on the VPS so it downloads "
                                         "history, or restart the terminal. Run scripts\\vps_check.ps1."))
                else:
                    log.warning(f"NO USABLE M15 DATA though the terminal reports connected "
                                f"(rates={'None' if m15_rates is None else len(m15_rates)}); fail count {mt5_fail_count}.")
                # Self-heal (2026-10-19): a reconnect can leave this process's MT5 session blind even after the network
                # returns. After 8 blind scans (~8 min) exit (the supervisor that restarted it was removed 2026-10-22).
                if mt5_fail_count >= 8:
                    msg = f"MT5 session blind for {mt5_fail_count} scans -- exiting so the watchdog restarts it."
                    log.error(msg)
                    try:
                        from src.core import alerts
                        alerts.send(f"MT5 still not answering after {mt5_fail_count} min: restarting the bot",
                                    alerts.WARN,
                                    action="Nothing yet. If this repeats, RDP in and check MT5 is logged in.")
                    except Exception:
                        pass
                    raise SystemExit(3)
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Atlas monitoring: update state and check DD/daily limits
            # ----------------------------------------------------------
            if ATLAS_MODE and atlas_engine and atlas_state:
                try:
                    _acct_atlas = mt5.account_info()
                    if _acct_atlas is not None:
                        _ai = _atlas_account_info(_acct_atlas)
                        atlas_engine.update_state(_ai, atlas_state, datetime.now(timezone.utc))
                        _save_atlas_state(atlas_state)
                        _mon = atlas_engine.monitor(_ai, atlas_state, datetime.now(timezone.utc))
                        if _mon == "FLATTEN":
                            log.error(f"ATLAS MONITOR: FLATTEN triggered — closing all positions.")
                            from src.core import alerts
                            _detail = atlas_engine.monitor_detail(_ai, atlas_state, datetime.now(timezone.utc))
                            _expiry = None
                            if _daily_only(_detail.reasons):       # owner 2026-10-30: resume at the next Atlas day
                                _expiry = datetime.combine(datetime.now(timezone.utc).date() + timedelta(days=1),
                                                           datetime.min.time(), tzinfo=timezone.utc)
                                alerts.send("Atlas daily limit: all trades closed, paused until tomorrow",
                                            alerts.WARN,
                                            context={"why": _explain_atlas(_detail.reasons),
                                                     "equity": f"${_ai.equity:,.2f}",
                                                     "resumes": _expiry.astimezone(IST).strftime("%a %H:%M IST")},
                                            action="Nothing to do: the bot restarts by itself at the new Atlas day.")
                            else:
                                alerts.send("Atlas safety stop: all trades closed, bot halted", alerts.CRITICAL,
                                            context={"why": _explain_atlas(_detail.reasons),
                                                     "equity": f"${_ai.equity:,.2f}"},
                                            action=HALT_CLEAR_HELP)
                            _close_all_positions(fetcher, executor, f"Atlas rule engine: {_detail.reasons}", None)
                            ops.set_halt(f"Atlas FLATTEN: {_detail.reasons}", "atlas_rule_engine", notify=False,
                                         expires_utc=_expiry)
                            break
                        elif _mon == "STOP_NEW":
                            _detail = atlas_engine.monitor_detail(_ai, atlas_state, datetime.now(timezone.utc))
                            log.warning(f"ATLAS MONITOR: STOP_NEW — {_detail.reasons}. "
                                        f"No new entries this scan.")
                            _manage_open_positions(fetcher, risk, executor)
                            _time.sleep(LOOP_INTERVAL)
                            continue
                        # Periodic eval progress log (every ~10 min)
                        if atlas_state.phase == "evaluation" and int(_time.time()) % 600 < LOOP_INTERVAL:
                            _prog = atlas_engine.evaluation_progress(
                                float(_acct_atlas.balance), atlas_state.initial_balance)
                            log.info(f"ATLAS EVAL: {_prog['progress']*100:.1f}% to target "
                                     f"(${_prog['profit_usd']:.2f}/${_prog['target_usd']:.2f})")
                except Exception as _ae:
                    log.warning(f"Atlas monitor check failed (fail-closed, skipping entries): {_ae}")
                    _manage_open_positions(fetcher, risk, executor)
                    _time.sleep(LOOP_INTERVAL)
                    continue

            # ----------------------------------------------------------
            # Gate 1: Spread filter (entries only; positions still managed)
            # ----------------------------------------------------------
            if not risk.is_spread_ok():
                _manage_open_positions(fetcher, risk, executor)
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Gate 1b: News blackout
            # ----------------------------------------------------------
            _news_blocked, _news_reason = news_filter.is_near_news_event(now_ist)
            if _news_blocked:
                log.info(f"NEWS FILTER: {_news_reason}")
                trade_alerts.news_pause(_news_reason)
                _manage_open_positions(fetcher, risk, executor)
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Gate 2: Dynamic daily drawdown cap
            # ----------------------------------------------------------
            todays_pl = fetcher.get_todays_closed_pl()
            floating_pl = fetcher.get_account_floating_pl()

            if not risk.check_daily_drawdown(
                todays_pl=todays_pl, floating_pl=floating_pl
            ) and not risk_rules.daily_cap_relaxed():
                drawdown_shutdown = True
                shutdown_date = now_ist.date()
                print(
                    f"[{_ist_now()}] SHUTDOWN: Daily drawdown limit hit "
                    f"(realised ${todays_pl:.2f} + floating ${floating_pl:.2f}). "
                    f"No more trades until midnight IST."
                )
                _manage_open_positions(fetcher, risk, executor)
                _time.sleep(LOOP_INTERVAL)
                continue

            d1_rates_macro = fetcher.get_d1_rates(60)
            d1_bias = order_flow.compute_d1_bias(d1_rates_macro)

            # Pass D1 rates to strategies that use them directly (V6+)
            if d1_rates_macro is not None:
                for s in strategies:
                    if hasattr(s, "set_d1_rates"):
                        s.set_d1_rates(d1_rates_macro)

            # ----------------------------------------------------------
            # Session info
            # ----------------------------------------------------------
            session_mult = risk.get_session_multiplier(now_ist)
            session_name = risk.get_session_name(now_ist)
            is_london = risk.is_london_open(now_ist)

            if session_name == "LONDON_NY_OVERLAP":
                _manage_open_positions(fetcher, risk, executor)
                _time.sleep(LOOP_INTERVAL)
                continue

            # ----------------------------------------------------------
            # Evaluate all strategies
            # ----------------------------------------------------------
            # Time of the last CLOSED candle -- the one strategies read at [-2].
            # It is the deduplication key: it stays constant for 15 minutes.
            signal_candle = int(m15_rates[-2]["time"])
            
            # Clear stale dedup entries based on candle timestamp
            stale_cutoff = signal_candle - 7200
            last_fired_candle = {k: v for k, v in last_fired_candle.items() if v is not None and v >= stale_cutoff}
            stale_order_cutoff = signal_candle - 86400  # 24 hours
            executed_orders_dedup = {k for k in executed_orders_dedup if k[1] >= stale_order_cutoff}
            EXECUTED_ORDERS_DEDUP.clear()
            EXECUTED_ORDERS_DEDUP.update(executed_orders_dedup)
            
            actionable_signals = order_flow.collect_actionable_signals(
                strategies, m15_rates, m5_rates, d1_bias, last_fired_candle,
                signal_candle, session_name, is_london)

            # ----------------------------------------------------------
            # HIGHLANDER RULE: Execute only the highest conviction signal
            # ----------------------------------------------------------
            order_flow.execute_best_signal(
                actionable_signals, last_fired_candle, signal_candle, m15_rates,
                fetcher, risk, executor, session_mult, session_name,
                executed_orders_dedup)

            # ----------------------------------------------------------
            # Manage open positions (consolidation exit)
            # ----------------------------------------------------------
            _manage_open_positions(fetcher, risk, executor)

        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            print(f"[{_ist_now()}] ERROR: {e}")

        _time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    run()
