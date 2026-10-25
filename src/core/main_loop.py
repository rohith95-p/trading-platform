"""
main_loop.py -- Ultra Core v3 Final Boss Orchestrator.

PHILOSOPHY:
  - NEVER hardcode dollar limits. Everything scales with ATR.
  - Fixed lots, positions run to their fixed SL/TP -- no trailing, no pyramiding.
  - Atlas mode: portfolio_atlas (DonchianTrend, AsianRangeFiltered, AsianBreakout).
  - Non-Atlas: portfolio_v6 (DonchianTrend only).
  - Sessions in IST; D1 bias gate disabled for V6 strategies.

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
import numpy as np
import MetaTrader5 as _mt5
from typing import Any, Optional
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

mt5: Any = _mt5

from src.core.data_fetcher import DataFetcher
from src.core.risk_manager import RiskManager
from src.core.execution_handler import ExecutionHandler, FIXED_LOT_SIZE
from src.core import resilience
from src.core import trade_log
from src.core import risk_rules
from src.core import market_hours
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
    AtlasRuleEngine, AtlasState, AccountInfo, OrderRequest, load_rules, RulesError,
)
from src.atlas.mcp_monitor import AtlasMCPMonitor

# IST offset
IST = timezone(timedelta(hours=5, minutes=30))

# P0-3: Global dedup set for (magic, bar_time, direction) to prevent duplicate fills
EXECUTED_ORDERS_DEDUP: set = set()

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

# Atlas Funded integration: enable with ULTRA_ATLAS_MODE=1 (env var).
# When on, portfolio_atlas replaces portfolio_v6, the AtlasRuleEngine gates
# every order, and the MCP monitor polls account health in the background.
ATLAS_MODE = os.environ.get("ULTRA_ATLAS_MODE", "0") == "1"

# Unverified rules the engine must acknowledge to load (see atlas_access.json).
_ATLAS_ALLOW_UNVERIFIED = ["daily_loss_eod_computation", "ea_approval_required"]

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

# D1 EMA20 direction gate -- ON. Reversed 2026-09-06 (HYP-064) after August 2026
# simulation proved that trading FVG strategies without trend filtering in a
# high-volatility environment causes extreme drawdowns. The gate flawlessly
# filtered out toxic counter-trend setups in August, turning a -79% maxDD failure
# into a +$44 profit (PF 1.40).
ENABLE_D1_GATE = True


def _ist_now() -> str:
    return datetime.now(IST).strftime("%I:%M:%S %p IST")


def _calc_ema(closes: np.ndarray, period: int) -> np.ndarray:
    ema = np.full_like(closes, np.nan, dtype=float)
    if len(closes) >= period:
        multiplier = 2.0 / (period + 1.0)
        ema[period - 1] = np.mean(closes[:period])
        for i in range(period, len(closes)):
            ema[i] = (closes[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def _init_atlas(balance: float, equity: float) -> tuple:
    """Load Atlas rules, create engine + state + MCP monitor. Returns (engine, state, monitor) or raises."""
    rules = load_rules(allow_unverified=_ATLAS_ALLOW_UNVERIFIED)
    engine = AtlasRuleEngine(rules)
    phase = os.environ.get("ULTRA_ATLAS_PHASE", "evaluation")
    now_utc = datetime.now(timezone.utc)
    state = AtlasState.new(initial_balance=balance, now_utc=now_utc, phase=phase, equity=equity)
    monitor = AtlasMCPMonitor(poll_interval=300.0)
    monitor.start()
    return engine, state, monitor


def _atlas_account_info(acct) -> AccountInfo:
    """Build an AccountInfo from an MT5 account_info() result."""
    return AccountInfo(
        balance=float(acct.balance),
        equity=float(acct.equity),
        margin=float(getattr(acct, "margin", 0.0) or 0.0),
        free_margin=float(getattr(acct, "margin_free", 0.0) or 0.0),
        ts_utc=datetime.now(timezone.utc),
        floating_pnl=float(acct.profit) if hasattr(acct, "profit") else None,
    )


def _close_all_positions(fetcher, executor, reason: str) -> None:
    """Flatten every open position on the symbol (kill switch)."""
    from src.core import alerts
    alerts.send(f"⚠️ KILL SWITCH ACTIVATED ⚠️\nReason: {reason}", severity=alerts.CRITICAL)
    # Own positions only. Foreign positions are reported, never closed, unless ULTRA_ACCOUNT_WIDE_FLATTEN=1.
    wide = scope.account_wide_flatten_enabled()
    targets = fetcher.get_positions() if wide else fetcher.get_own_positions()
    foreign_left = [] if wide else fetcher.get_foreign_positions()
    if foreign_left:
        log.warning(f"KILL SWITCH: leaving {len(foreign_left)} foreign position(s) untouched: {scope.foreign_report(foreign_left)}")
    for pos in targets:
        if executor.close_position(pos):
            log.warning(f"KILL SWITCH: closed #{pos.ticket} ({reason})")
        else:
            log.error(f"KILL SWITCH: FAILED to close #{pos.ticket} -- close it manually.")
            alerts.send(f"🚨 KILL SWITCH FAILED to close #{pos.ticket} -- close it manually!", severity=alerts.CRITICAL)


def run():
    """Main entry point."""

    # Single-instance guard -- refuse to start if another main_loop is alive.
    if not resilience.acquire_lock():
        return

    try:
        _run_guarded()
    finally:
        resilience.release_lock()


def _run_guarded():
    if not mt5.initialize():
        log.error("MT5 initialisation failed. Exiting.")
        return

    # Startup safety: right account, tradeable connection, symbol present.
    if not resilience.startup_safety_check(mt5, SYMBOL):
        log.error("Startup safety check FAILED. Not trading. Fix the above and restart.")
        return

    # Persistent halt latch (2026-10-18): a halt survives crashes and restarts and is cleared only by a deliberate
    # operator action (python -m scripts.halt clear --note "...").
    _halt = ops.halt_status()
    if _halt is not None:
        from src.core import alerts
        msg = (f"START REFUSED: halt latch is set ({_halt.get('source')}: {_halt.get('reason')}). "
               f"Review, reconcile, then clear with: python -m scripts.halt clear --note \"...\"")
        log.error(msg)
        alerts.send(msg, severity=alerts.CRITICAL)
        return
    if ops.measure_only():
        log.warning("MEASUREMENT-ONLY MODE (ULTRA_MEASURE_ONLY): scanning and logging, NO orders will be sent.")
    risk_rules.LIVE_CONTEXT = True   # lets risk_rules relax the monthly/peak hard halts, and only on a DEMO account
    _active_portfolio = PORTFOLIO_ATLAS if ATLAS_MODE else PORTFOLIO_V6
    try:
        _own = scope.load_own_magics()
        _missing = scope.check_portfolio_magics(_active_portfolio, _own)
    except scope.ScopeConfigError as e:
        log.error(f"START REFUSED: {e}")
        return
    if _missing:
        log.error(f"START REFUSED: PORTFOLIO magics {_missing} are not in config/ultra_magics.json")
        return
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
            return
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
            return
    if not ops.measure_only() and scope.block_on_foreign_enabled():
        _foreign0 = fetcher.get_foreign_exposure()
        if _foreign0:
            from src.core import alerts
            _msg = (f"START REFUSED: another system holds positions on {SYMBOL} while orders are enabled: "
                    f"{scope.foreign_report(_foreign0)}. Use measurement-only mode, a separate account, "
                    f"or close them manually.")
            log.error(_msg)
            alerts.send(_msg, severity=alerts.CRITICAL)
            return
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
            return
        except Exception as e:
            log.error(f"ATLAS: unexpected init error: {e}")
            return

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
             f"D1 gate: {'ON' if ENABLE_D1_GATE else 'OFF'}")
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
                log.info("Midnight IST transition detected. Running daily tasks.")
                try:
                    from src.core.daily_report import send_daily_report
                    send_daily_report(force=False)
                except Exception as e:
                    log.error(f"Failed to send daily report: {e}")
                current_date = now_ist.date()
            resilience.heartbeat()
            _push_ops_heartbeat(fetcher, drawdown_shutdown)  # external dead-man heartbeat (status payload)
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
                    _close_all_positions(fetcher, executor, "Weekend Gap Avoidance")
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
            got_data = conn_ok and m15_rates is not None and len(m15_rates) >= 200
            mt5_fail_count = resilience.note_fetch_result(mt5, got_data, mt5_fail_count, reason=conn_reason)
            if not got_data:
                if not conn_ok:
                    log.warning(f"LIVENESS CHECK FAILED: {conn_reason}. Skipping signal evaluation.")
                else:
                    log.warning(f"NO USABLE M15 DATA though the terminal reports connected "
                                f"(rates={'None' if m15_rates is None else len(m15_rates)}); fail count {mt5_fail_count}.")
                # Self-heal (2026-10-19): a reconnect can leave this process's MT5 session blind even after the network
                # returns. After 8 blind scans (~8 min) exit (the supervisor that restarted it was removed 2026-10-22).
                if mt5_fail_count >= 8:
                    msg = f"MT5 session blind for {mt5_fail_count} scans -- exiting; restart the bot by hand."
                    log.error(msg)
                    try:
                        from src.core import alerts
                        alerts.send(f"⚠️ {msg}", severity=alerts.CRITICAL)
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
                        _mon = atlas_engine.monitor(_ai, atlas_state, datetime.now(timezone.utc))
                        if _mon == "FLATTEN":
                            log.error(f"ATLAS MONITOR: FLATTEN triggered — closing all positions.")
                            from src.core import alerts
                            _detail = atlas_engine.monitor_detail(_ai, atlas_state, datetime.now(timezone.utc))
                            alerts.send(f"🚨 ATLAS FLATTEN: {_detail.reasons}", severity=alerts.CRITICAL)
                            _close_all_positions(fetcher, executor, f"Atlas rule engine: {_detail.reasons}")
                            ops.set_halt(f"Atlas FLATTEN: {_detail.reasons}", "atlas_rule_engine")
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

            d1_bias = None
            d1_rates_macro = fetcher.get_d1_rates(60)
            if ENABLE_D1_GATE:
                if d1_rates_macro is not None and len(d1_rates_macro) >= 21:
                    # get_d1_rates() uses copy_rates_from_pos(..., 0, n), whose
                    # index 0 (and therefore [-1]) is today's still-forming D1
                    # candle, not the last closed one. Every other bias/signal
                    # check in this file reads the closed bar at [-2]
                    # (see signal_candle above); this gate previously read
                    # [-1] directly, letting the daily bias flip intraday as
                    # gold moves rather than only on a closed daily candle.
                    d1_closes = d1_rates_macro["close"]
                    d1_opens  = d1_rates_macro["open"]
                    d1_ema20 = _calc_ema(d1_closes, 20)
                    if not np.isnan(d1_ema20[-2]):
                        d1_bias = "BULLISH" if d1_closes[-2] > d1_ema20[-2] else "BEARISH"
                        log.info(
                            f"D1 GATE: close[-2]={d1_closes[-2]:.2f}  EMA20={d1_ema20[-2]:.2f}  "
                            f"→ bias={d1_bias}"
                        )

                    # ----------------------------------------------------------
                    # P2: Supplementary intraday override.
                    # If the LIVE (still-forming) D1 bar has already moved
                    # >= 2× D1 ATR against the closed-bar bias, the closed bar
                    # is stale and we flip the bias to match the intraday move.
                    # This catches crash days like 2026-09-28 where the prior
                    # close was barely above EMA20 (BULLISH) but the day opened
                    # and immediately sold off 100+ pts.
                    # ----------------------------------------------------------
                    _D1_INTRADAY_OVERRIDE_MULT = 1.0   # >=1.0x ATR intraday move overrides previous day's stale close
                    if d1_bias is not None and len(d1_closes) >= 15:
                        _d1_atr_arr = np.abs(np.diff(d1_closes[-15:]))
                        _d1_atr = float(np.median(_d1_atr_arr)) if len(_d1_atr_arr) else 0.0
                        _live_open  = float(d1_opens[-1])
                        _live_close = float(d1_closes[-1])
                        _intraday_move = _live_close - _live_open  # + = up, - = down
                        if _d1_atr > 0:
                            _move_ratio = abs(_intraday_move) / _d1_atr
                            if _move_ratio >= _D1_INTRADAY_OVERRIDE_MULT:
                                _intraday_bias = "BULLISH" if _intraday_move > 0 else "BEARISH"
                                if _intraday_bias != d1_bias and not _override_may_apply(d1_bias, _intraday_bias):
                                    # 2026-10-17 (owner rule): a BEARISH daily trend must keep blocking buys.
                                    # The override may only TIGHTEN (bullish -> bearish on a crash day), never
                                    # loosen (bearish -> bullish), which is how counter-trend buys got through
                                    # on 2026-10-15.
                                    log.warning(
                                        f"D1 INTRADAY OVERRIDE SUPPRESSED: live bar {_intraday_move:+.1f} pts "
                                        f"({_move_ratio:.1f}×ATR) points {_intraday_bias} but the daily trend is "
                                        f"{d1_bias}; bias stays {d1_bias}."
                                    )
                                elif _intraday_bias != d1_bias:
                                    log.warning(
                                        f"D1 INTRADAY OVERRIDE: live bar moved "
                                        f"{_intraday_move:+.1f} pts ({_move_ratio:.1f}×ATR). "
                                        f"Overriding stale {d1_bias} → {_intraday_bias}."
                                    )
                                    d1_bias = _intraday_bias
                                else:
                                    log.info(
                                        f"D1 INTRADAY CHECK: move {_intraday_move:+.1f} pts "
                                        f"({_move_ratio:.1f}×ATR) — confirms {d1_bias}."
                                    )

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
            
            actionable_signals = []

            for strategy in strategies:
                # Check pending confirmation (non-London signals)
                confirmed_signal = strategy.check_pending_confirmation(m15_rates)
                if confirmed_signal is not None:
                    if last_fired_candle.get(strategy.name) == signal_candle:
                        log.info(f"[{strategy.name}] confirmed signal DEDUPED (already acted this candle).")
                    else:
                        log.info(f"Pending signal CONFIRMED ({strategy.name}): {confirmed_signal.direction_str}")
                        if _d1_bias_allows(confirmed_signal, d1_bias, strategy.name, strategy):
                            actionable_signals.append((strategy, confirmed_signal))

                # Evaluate strategy
                signal = strategy.evaluate(m15_rates, m5_rates)

                if signal is not None:
                    if last_fired_candle.get(strategy.name) == signal_candle:
                        trade_log.signal(strategy.name, signal.direction_str, "deduped",
                                         "already acted on this candle", candle=signal_candle,
                                         session=session_name)
                        continue
                    if not _d1_bias_allows(signal, d1_bias, strategy.name, strategy):
                        trade_log.signal(strategy.name, signal.direction_str, "blocked",
                                         f"D1 bias gate ({d1_bias})", candle=signal_candle,
                                         session=session_name)
                        continue
                    if _leg_in_cooldown(strategy.name):
                        log.info(f"[{strategy.name}] {signal.direction_str} skipped -- reversal cooldown active.")
                        trade_log.signal(strategy.name, signal.direction_str, "blocked",
                                         "reversal cooldown active", candle=signal_candle,
                                         session=session_name)
                        continue

                    if is_london or getattr(strategy, "execute_immediately", False):
                        log.info(f"[{strategy.name}] {signal.direction_str} -- actionable immediately (session={session_name})")
                        actionable_signals.append((strategy, signal))
                    else:
                        candle_time = int(m15_rates[-2]["time"])
                        strategy.set_pending(signal, candle_time)
                        log.info(f"Signal queued for confirmation ({strategy.name} in {session_name}): {signal.direction_str}")
                        print(f"[{_ist_now()}] PENDING: {signal.direction_str} signal queued (session: {session_name}). Confirming next candle.")

            # ----------------------------------------------------------
            # HIGHLANDER RULE: Execute only the highest conviction signal
            # ----------------------------------------------------------
            if actionable_signals:
                # Rank by conviction based on validated risk-adjusted expectancy
                rank_order = {
                    "DONCHIAN_TREND_V6": 7,
                    "ASIAN_RANGE_FILTERED_V6": 6,
                    "ASIAN_BREAKOUT_V6": 6,
                }
                
                # Sort signals by rank (descending)
                actionable_signals.sort(key=lambda x: rank_order.get(x[0].name.upper(), 0), reverse=True)
                
                best_strategy, best_signal = actionable_signals[0]
                
                if len(actionable_signals) > 1:
                    log.info(f"HIGHLANDER: {len(actionable_signals)} signals fired. Selected {best_strategy.name} as best conviction.")
                
                # Execute the best one
                _TRANSIENT_BLOCK["flag"] = False
                _execute_signal(
                    best_signal, m15_rates, fetcher, risk, executor,
                    session_mult, session_name, best_strategy,
                    executed_orders_dedup=executed_orders_dedup,
                )
                # 2026-10-19: spread on XAUUSDm alternates 240/260 pts and the legs' cap is 250, so one 260-pt tick
                # used to burn the whole candle's signal (dedup). Retry next scan (up to 10 times per candle) instead.
                _rk = (best_strategy.name, signal_candle)
                if _TRANSIENT_BLOCK["flag"] and _SPREAD_RETRIES.get(_rk, 0) < 10:
                    _SPREAD_RETRIES[_rk] = _SPREAD_RETRIES.get(_rk, 0) + 1
                    for _k in [k for k in _SPREAD_RETRIES if k[1] < signal_candle - 7200]:
                        _SPREAD_RETRIES.pop(_k, None)
                    log.info(f"[{best_strategy.name}] spread block is transient -- will retry on this candle "
                             f"(attempt {_SPREAD_RETRIES[_rk]}/10).")
                else:
                    last_fired_candle[best_strategy.name] = signal_candle
                
                # Block the others and mark them as fired to prevent immediate re-fires
                for strat, sig in actionable_signals[1:]:
                    trade_log.signal(strat.name, sig.direction_str, "blocked",
                                     f"Highlander rule: overridden by {best_strategy.name}", candle=signal_candle,
                                     session=session_name)
                    log.info(f"[{strat.name}] {sig.direction_str} BLOCKED by Highlander rule (lost to {best_strategy.name}).")
                    last_fired_candle[strat.name] = signal_candle

            # ----------------------------------------------------------
            # Pyramiding: add to winning positions
            # ----------------------------------------------------------
            if ENABLE_PYRAMIDING:
                _check_pyramiding(fetcher, risk, executor, m15_rates, session_mult,
                                  session_name, now_ist=now_ist)

            # ----------------------------------------------------------
            # Manage open positions (trailing + consolidation)
            # ----------------------------------------------------------
            _manage_open_positions(fetcher, risk, executor)

        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)
            print(f"[{_ist_now()}] ERROR: {e}")

        _time.sleep(LOOP_INTERVAL)


_COOLDOWN_FILE = os.path.join(resilience._LOGS, "cooldown.json")


_LAST_HB = {"t": None}
_FOREIGN_SEEN = {"tickets": None}
_TRANSIENT_BLOCK = {"flag": False}     # set by _execute_signal when the block is momentary (spread blip)
_SPREAD_RETRIES: dict = {}             # (strategy, candle) -> retries used
_ATLAS_RT: dict = {}                   # populated by _run_guarded when ATLAS_MODE is on


def _alert_foreign_exposure(foreign) -> None:
    """Alert when the foreign ticket set changes, and re-alert every 30 min while it persists."""
    tickets = tuple(sorted(p.ticket for p in foreign))
    if tickets == _FOREIGN_SEEN["tickets"] and (not foreign or _time.time() - _FOREIGN_SEEN.get("t", 0) < 1800):
        return
    _FOREIGN_SEEN["t"] = _time.time()
    prev, _FOREIGN_SEEN["tickets"] = _FOREIGN_SEEN["tickets"], tickets
    if not foreign:
        if prev:
            log.info("Foreign exposure cleared.")
        return
    rep = scope.foreign_report(foreign)
    msg = (f"FOREIGN EXPOSURE DETECTED on {SYMBOL}: {rep}. New Ultra Core entries are blocked; "
           f"foreign positions are left untouched.")
    log.error(msg)
    trade_log.gate("foreign_exposure", allowed=False, reason="another system holds positions on this symbol",
                   foreign=rep, risk_scope="account")
    try:
        from src.core import alerts
        alerts.send(msg, severity=alerts.CRITICAL)
    except Exception:
        pass


def _push_ops_heartbeat(fetcher, drawdown_shutdown: bool) -> None:
    """Send the status heartbeat. Never raises and never blocks the loop (push runs in a daemon thread)."""
    try:
        now = _time.time()
        interval = None if _LAST_HB["t"] is None else now - _LAST_HB["t"]
        _LAST_HB["t"] = now
        tick = fetcher.get_tick()
        quote_age = (now - float(tick.time)) if tick is not None else None
        orders = mt5.orders_get(symbol=SYMBOL)
        acct = mt5.account_info()
        mode = {0: "demo", 1: "contest", 2: "real"}.get(getattr(acct, "trade_mode", None), "unknown") if acct else "unknown"
        payload = ops.build_status(
            account=mode, scan_interval_s=interval, quote_age_s=quote_age,
            open_positions=len(fetcher.get_own_positions()), pending_orders=len(orders) if orders else 0,
            daily_pnl=fetcher.get_todays_closed_pl(), drawdown_shutdown=drawdown_shutdown)
        payload["foreign_positions"] = len(fetcher.get_foreign_positions())
        ops.push_status(payload)
    except Exception as e:
        log.debug(f"ops heartbeat skipped: {e}")


def _leg_in_cooldown(name: str) -> bool:
    """True if scripts/protect_profit.py closed this leg on a reversal recently
    and it should not re-enter yet."""
    try:
        import json as _json
        with open(_COOLDOWN_FILE) as f:
            until = _json.load(f).get(name, 0)
        # pyrefly: ignore [no-any-return-implicit]
        return _time.time() < until
    except (OSError, ValueError):
        return False


def _record_closed_trades(fetcher, known_tickets):
    """Feed every newly-closed position's realised P/L to the risk_rules streak
    breakers (II.4: consecutive-loss pause / stop-day, early-phase losing-trade
    cap).

    `record_trade_result()` existed but nothing ever called it, so
    consecutive_losses / day_losing_trades sat at 0 forever and those breakers
    could not fire even in shadow mode. This closes that gap. It is still
    shadow-only while risk_rules.ENFORCE is False -- it makes the breaker STATE
    real (persisted to logs/risk_state.json) so it can be measured now and works
    the moment ENFORCE is flipped on.

    known_tickets is None on the first loop after startup -- pre-existing
    positions are adopted, not counted as closes. A ticket whose deal history
    can't be read yet is retried next loop rather than lost.
    """
    current = {p.ticket for p in fetcher.get_own_positions()}   # strategy view: foreign closes never feed our streak breakers
    if known_tickets is None:
        return current

    closed = known_tickets - current
    if not closed:
        return current

    acct = mt5.account_info()
    state = risk_rules.load_state()
    if acct is not None:
        # same day/week/month roll evaluate() does, so a close before the first
        # signal of a new day sees a reset day_losing_trades.
        state = risk_rules._roll_anchors(state, float(acct.balance), datetime.now(IST))

    still_pending = set()
    for ticket in closed:
        try:
            deals = mt5.history_deals_get(position=ticket)
            if not deals:
                still_pending.add(ticket)
                continue
            out_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
            if not out_deals:
                # Position still open / exit deal not yet visible: retry next loop
                # rather than recording a phantom $0 "win" that resets the streak.
                still_pending.add(ticket)
                continue
            pl = sum((d.profit + d.swap + d.commission) for d in out_deals)
            in_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
            strat_name = (in_deals[0].comment if in_deals else deals[0].comment) or "Unknown"
            state = risk_rules.record_trade_result(pl, state=state)
            trade_log.position_closed(strategy=strat_name, ticket=ticket, profit=round(pl, 2),
                                      consecutive_losses=state.consecutive_losses,
                                      day_losing_trades=state.day_losing_trades,
                                      streak_pause_active=state.pause_until_ts > _time.time(),
                                      enforced=risk_rules.ENFORCE, risk_scope="strategy",
                                      magic=(in_deals[0].magic if in_deals else None))
            
            # Notify exit
            from src.core import alerts
            icon = "✅" if pl > 0 else "❌"
            
            _acct = mt5.account_info()
            bal_str = f"${_acct.balance:.2f}" if _acct else "Unknown"
            float_str = f"${_acct.profit:.2f}" if _acct else "Unknown"
            
            now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            log_msg = f"{icon} EXIT: {strat_name} (Ticket #{ticket}) | Trade P&L: ${pl:.2f} | Floating: {float_str} | Balance: {bal_str}"
            
            # Formatted columns for Telegram
            tg_msg = (
                f"{icon} TRADE CLOSED\n"
                f"Time     | {now_str}\n"
                f"Strategy | {strat_name}\n"
                f"Ticket   | #{ticket}\n"
                f"P&L      | ${pl:.2f}\n"
                f"Floating | {float_str}\n"
                f"Balance  | {bal_str}\n"
            )
            alerts.send(tg_msg, severity=alerts.INFO)
            
        except Exception as e:
            log.warning(f"streak breaker: could not record close of #{ticket}: {e}")
            still_pending.add(ticket)

    risk_rules.save_state(state)
    
    if closed:
        _check_vi3_tripwire(fetcher)

    return current | still_pending


def _check_vi3_tripwire(fetcher):
    """VI.3 tripwire: monitor rolling 30-trade live profit factor."""
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=60)
        deals = mt5.history_deals_get(start, now)
        if not deals:
            return
            
        magics = {int(cls().magic) for cls in (PORTFOLIO_ATLAS if ATLAS_MODE else PORTFOLIO_V6)}
        pls = []
        for d in deals:
            if d.symbol == fetcher.symbol and d.magic in magics and d.entry == mt5.DEAL_ENTRY_OUT:
                pl = float(d.profit) + float(d.swap) + float(d.commission)
                pls.append((int(d.time), pl))
                
        if len(pls) < 30:
            return
            
        pls.sort(key=lambda x: x[0])
        recent_30 = [x[1] for x in pls[-30:]]
        
        arr = np.array(recent_30, dtype=float)
        w, l = arr[arr > 0], arr[arr < 0]
        pf = float(w.sum() / -l.sum()) if len(l) else float("inf")
        
        if pf < 0.8:
            msg = f"VI.3 TRIPWIRE: Rolling 30-trade PF is {pf:.2f} (<0.8). Logging only (kill switch disabled by user)."
            log.error(msg)
            from src.core import alerts
            alerts.send(msg, severity=alerts.CRITICAL)
            # Kill switch disabled
        elif pf < 1.0:
            msg = f"VI.3 TRIPWIRE WARN: Rolling 30-trade PF is {pf:.2f} (<1.0)."
            log.warning(msg)
            from src.core import alerts
            alerts.send(msg, severity=alerts.WARN)
    except Exception as e:
        log.warning(f"Could not check VI.3 tripwire: {e}")


def _override_may_apply(closed_bias: str, intraday_bias: str) -> bool:
    """The intraday override may only make the gate STRICTER: a bullish daily trend turning
    bearish on a crash day. A bearish daily trend is never flipped to bullish (owner rule 2026-10-17)."""
    return closed_bias == "BULLISH" and intraday_bias == "BEARISH"


def _d1_bias_allows(signal, d1_bias, strategy_name: str, strategy=None) -> bool:
    """Daily-trend gate, shared by the fresh and confirmed signal paths.

    Previously only fresh signals were gated; confirmed pending signals executed
    without ever consulting the daily bias.

    Fails CLOSED (2026-10-17): with the gate enabled, no bias (short/failed D1 fetch, NaN EMA)
    means no new entry, instead of silently trading both directions.

    Strategies with skip_d1_gate=True (V6+) bypass this gate because they have
    their own internal trend filter.
    """
    if strategy is not None and getattr(strategy, "skip_d1_gate", False):
        return True
    if not d1_bias:
        if ENABLE_D1_GATE:
            log.warning(f"[{strategy_name}] entry blocked: D1 gate enabled but the daily bias could not be computed.")
            return False
        return True
    if signal.is_buy and d1_bias == "BEARISH":
        log.info(f"[{strategy_name}] BUY blocked by D1 BEARISH bias.")
        return False
    if not signal.is_buy and d1_bias == "BULLISH":
        log.info(f"[{strategy_name}] SELL blocked by D1 BULLISH bias.")
        return False
    return True


def _execute_signal(signal, m15_rates, fetcher, risk, executor, session_mult, session_name, strategy=None, executed_orders_dedup=None):
    """Calculate stops and execute a signal.

    `strategy` is optional so every existing caller keeps working unchanged.
    When the firing strategy carries its own `sl_atr_mult`/`tp_atr_mult`
    (portfolio_v4 legs, rohith phase 3), those override the session-default
    multiplier and the shared TP_ATR_MULTIPLIER constant for this order only.
    Absent on a strategy -> falls back to exactly the prior behaviour.
    """
    # Measurement-only mode (2026-10-18): signals are logged, no order of any kind is sent.
    if ops.measure_only():
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         "measurement-only mode (no orders)", session=session_name)
        return None

    # Foreign exposure (2026-10-18): another system holds positions on our symbol -> fail closed, never touch them.
    if scope.block_on_foreign_enabled():
        foreign = fetcher.get_foreign_exposure()
        if foreign:
            _alert_foreign_exposure(foreign)
            trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                             "FOREIGN EXPOSURE DETECTED (another system holds positions on this symbol)",
                             session=session_name, risk_scope="account")
            return None

    # IV.6 + owner's 11:30-21:30 trading window: weekend gap, rollover spread
    # spike, and no-night-trades are all checked here, before anything else.
    _mh_ok, _mh_why = market_hours.allow_new_entry()
    if not _mh_ok:
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         _mh_why, session=session_name)
        log.info(f"[{signal.strategy_name}] entry blocked -- {_mh_why}")
        return

    if strategy and getattr(strategy, "max_spread_pts", None):
        max_spread = strategy.max_spread_pts
        if not risk.is_spread_ok(max_spread):
            trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                             f"spread > {max_spread}", session=session_name)
            log.info(f"[{signal.strategy_name}] entry blocked -- spread > {max_spread}")
            _TRANSIENT_BLOCK["flag"] = True       # a momentary spread blip must not spend the candle's signal
            return

    if not executor.can_open_new_position():
        log.info("Cannot execute: max concurrent positions reached.")
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         "max concurrent positions reached", session=session_name)
        return

    tick = fetcher.get_tick()
    if tick is None:
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         "no tick available", session=session_name)
        return

    price = tick.ask if signal.is_buy else tick.bid

    sl_mult = getattr(strategy, "sl_atr_mult", None) or session_mult
    tp_mult = getattr(strategy, "tp_atr_mult", None)
    stops = risk.calculate_atr_stops(price, signal.is_buy, m15_rates, sl_mult, tp_mult)
    if stops is None:
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         "ATR stops unavailable", session=session_name)
        return

    # Part II shadow mode: record what the (not yet enforced) risk rulebook
    # would have decided, so its real-world impact can be measured before
    # ENFORCE is ever switched on. See src/core/risk_rules.py.
    try:
        _acct = mt5.account_info()
        if _acct is not None:
            _decision, _rstate = risk_rules.evaluate(
                balance=_acct.balance, equity=_acct.equity,
                margin_used=getattr(_acct, "margin", 0.0) or 0.0)
            risk_rules.save_state(_rstate)
            if not _decision.allow_new_entries:
                if str(_decision.reason).startswith("HARD HALT"):
                    ops.set_halt(_decision.reason, "risk_rules")   # latch: survives restarts, human clears it
                trade_log.gate("risk_rules_shadow", allowed=False, reason=_decision.reason,
                               strategy=signal.strategy_name, enforced=risk_rules.ENFORCE)
                if risk_rules.ENFORCE:
                    log.warning(f"[{signal.strategy_name}] BLOCKED by risk rules: {_decision.reason}")
                    return
    except Exception as _e:  # shadow logging must never break execution
        log.debug(f"risk_rules shadow evaluation skipped: {_e}")

    # Atlas rule engine pre-trade gate
    if ATLAS_MODE and _ATLAS_RT.get("engine") and _ATLAS_RT.get("state"):
        try:
            _acct_at = mt5.account_info()
            if _acct_at is not None:
                _ai_at = _atlas_account_info(_acct_at)
                _atr_val = risk.get_latest_atr(m15_rates) or 0.0
                _stop_risk = float(FIXED_LOT_SIZE * 100.0 * _atr_val * (getattr(strategy, "sl_atr_mult", 2.0) or 2.0))
                _margin_req = float(FIXED_LOT_SIZE * price * 100.0 / 50.0)  # 1:50 leverage
                _ord = OrderRequest(
                    symbol=SYMBOL, stop_risk_usd=_stop_risk,
                    margin_required=_margin_req, volume=FIXED_LOT_SIZE,
                    side="buy" if signal.is_buy else "sell")
                _news = _ATLAS_RT["monitor"].get_news_events() if _ATLAS_RT.get("monitor") else None
                _decision = _ATLAS_RT["engine"].check_order(
                    _ord, _ai_at, _ATLAS_RT["state"], datetime.now(timezone.utc), _news)
                if not _decision.allow:
                    log.warning(f"[{signal.strategy_name}] ATLAS GATE BLOCKED: {_decision.reasons}")
                    trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                                     f"Atlas rule engine: {_decision.reasons}", session=session_name)
                    return None
        except Exception as _ae:
            log.warning(f"Atlas pre-trade gate error (fail-closed): {_ae}")
            trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                             f"Atlas pre-trade gate error: {_ae}", session=session_name)
            return None

    # P0-3: Strict deduplication before placing order: (strategy_magic, bar_time, direction)
    bar_time = int(m15_rates[-2]["time"]) if m15_rates is not None and len(m15_rates) >= 2 else 0
    dir_str = signal.direction_str.upper()
    dedup_key = (int(signal.magic), bar_time, dir_str)

    dedup_set = executed_orders_dedup if executed_orders_dedup is not None else EXECUTED_ORDERS_DEDUP
    if dedup_key in dedup_set:
        log.warning(
            f"[{signal.strategy_name}] DUPLICATE ORDER BLOCKED by key {dedup_key} "
            f"(order already placed for bar {bar_time}). Refusing duplicate fill."
        )
        trade_log.signal(
            signal.strategy_name, signal.direction_str, "deduped",
            f"duplicate order key {dedup_key}", candle=bar_time,
            session=session_name
        )
        return None

    # Owner's rule: fixed 0.02 lots, no dynamic sizing. The 0.15 risk_pct sizer
    # put 0.02-0.03 lots on a ~$105 account (live, 2026-09-02). ExecutionHandler
    # also hard-caps this, but the call site now states the intent.
    lot_size = FIXED_LOT_SIZE

    result = executor.send_order(
        signal=signal.direction,
        price=price,
        sl=stops.sl,
        tp=stops.tp,
        strategy_name=signal.strategy_name,
        magic=signal.magic,
        lot_size=lot_size,
        atr=stops.atr,
        session=session_name,
    )

    dedup_set.add(dedup_key)

    if result is None:
        # Vetoed, blocked or rejected: no order exists, so none is logged as one.
        trade_log.signal(signal.strategy_name, signal.direction_str, "blocked",
                         "order not placed (veto/cap/broker reject)", candle=bar_time,
                         session=session_name)
        return None

    trade_log.order(
        strategy=signal.strategy_name, direction=signal.direction_str,
        lots=getattr(result, "lots", lot_size),
        price=price, sl=stops.sl, tp=stops.tp,
        retcode=getattr(result, "retcode", None),
        ticket=getattr(result, "order", None),
        atr=stops.atr, sl_atr_mult=sl_mult, tp_atr_mult=tp_mult,
        session=session_name, magic=signal.magic,
        bar_time=bar_time,
        dedup_key=f"{signal.magic}:{bar_time}:{dir_str}",
    )
    
    # Notify entry
    if getattr(result, "retcode", None) == mt5.TRADE_RETCODE_DONE:
        from src.core import alerts
        _acct = mt5.account_info()
        bal_str = f"${_acct.balance:.2f}" if _acct else "Unknown"
        float_str = f"${_acct.profit:.2f}" if _acct else "Unknown"
        msg = f"🟢 ENTRY: {signal.direction_str} {lot_size} lots\nStrategy: {signal.strategy_name}\nPrice: {price}\nSL: {stops.sl}\nTP: {stops.tp}\nFloating P&L: {float_str}\nAccount Balance: {bal_str}"
        alerts.send(msg, severity=alerts.INFO)
        
    return result


def _check_pyramiding(fetcher, risk, executor, m15_rates, session_mult, session_name,
                      now_ist=None):
    """Check if any open position qualifies for pyramiding.

    MED-14: this path had no session check at all, so a strategy gated to
    "London Open only" could add exposure at 04:30 IST. Backtesting found 50
    such entries scattered across hours 00-08 and 21-23. Pyramiding is now
    confined to the hours the strategies themselves trade (11:30-21:30 IST).
    """
    positions = fetcher.get_own_positions()
    if not positions:
        return

    now_ist = now_ist or datetime.now(IST)
    tv = now_ist.hour + now_ist.minute / 60.0
    if not (11.5 <= tv < 21.5):
        return

    if not executor.can_open_new_position():
        return

    curr_atr = risk.get_latest_atr(m15_rates)
    if curr_atr is None:
        return

    for pos in positions:
        is_buy = pos.type == mt5.ORDER_TYPE_BUY
        if risk.check_pyramid_condition(pos.price_open, pos.price_current, curr_atr, is_buy):
            # Check if we already pyramided this position (look for matching magic+direction)
            existing = [p for p in positions if p.type == pos.type and p.magic == pos.magic]
            if len(existing) >= 2:
                continue  # Already pyramided

            tick = fetcher.get_tick()
            if tick is None:
                continue

            price = tick.ask if is_buy else tick.bid
            stops = risk.calculate_atr_stops(price, is_buy, m15_rates, session_mult)
            if stops is None:
                continue

            lot_size = FIXED_LOT_SIZE  # owner's rule: pyramid adds are also 0.02

            profit_dist = abs(pos.price_current - pos.price_open)
            log.info(
                f"PYRAMID: {pos.comment} moved {profit_dist:.2f} in profit "
                f"(threshold: {0.5 * curr_atr:.2f}). Adding position."
            )

            executor.send_order(
                signal=mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                price=price,
                sl=stops.sl,
                tp=stops.tp,
                strategy_name=pos.comment.replace("_PYR", ""),
                magic=pos.magic,
                lot_size=lot_size,
                atr=stops.atr,
                session=session_name,
                is_pyramid=True,
            )
            break  # Only pyramid once per cycle


def _manage_open_positions(fetcher, risk, executor):
    """Run trailing stop logic and consolidation exit checks (own positions only)."""
    positions = fetcher.get_own_positions()
    if not positions:
        return

    m15_rates = fetcher.get_m15_rates(20)
    if m15_rates is None:
        return

    curr_atr = risk.get_latest_atr(m15_rates)
    if curr_atr is None:
        return
        
    try:
        import json
        import os as _os
        _vsl_path = _os.path.join(resilience._LOGS, "virtual_sl.json")
        with open(_vsl_path, "r") as f:
            virtual_sls = json.load(f)
    except Exception:
        virtual_sls = {}
        
    state_changed = False

    for pos in positions:
        # Trailing stop -- OFF by default, see ENABLE_TRAILING above.
        if ENABLE_TRAILING:
            ticket_str = str(pos.ticket)

            # `pos` comes straight from mt5.positions_get() -- MetaTrader5's
            # TradePosition is a read-only C struct sequence (subclasses
            # tuple), so `pos.sl = ...` raises AttributeError on a real
            # connection. Build a plain, mutable stand-in instead of
            # mutating the broker object in place.
            effective_sl = pos.sl
            if CLOSE_ONLY_TRAIL and ticket_str in virtual_sls:
                effective_sl = virtual_sls[ticket_str]

            trail_input = SimpleNamespace(
                sl=effective_sl,
                price_current=pos.price_current,
                price_open=pos.price_open,
                type=pos.type,
            )
            new_sl = risk.calculate_trailing_stop(trail_input, curr_atr)

            if new_sl is not None:
                if CLOSE_ONLY_TRAIL:
                    virtual_sls[ticket_str] = new_sl
                    state_changed = True
                    log.info(f"Virtual Trailing SL for #{pos.ticket} updated to {new_sl}")
                else:
                    executor.modify_sl(pos.ticket, new_sl, pos.tp, pos.symbol)
                    
            if CLOSE_ONLY_TRAIL and ticket_str in virtual_sls:
                v_sl = virtual_sls[ticket_str]
                is_buy = pos.type == 0 # mt5.ORDER_TYPE_BUY
                last_closed_bar = m15_rates[-2]
                close_price = float(last_closed_bar["close"])
                
                # Check if the closed candle violated our virtual SL
                if is_buy and close_price <= v_sl:
                    log.warning(f"CLOSE-ONLY TRAIL HIT: #{pos.ticket} long closed at {close_price} (SL: {v_sl})")
                    executor.close_position(pos)
                    continue # Skip consolidation check since it's closed
                elif not is_buy and close_price >= v_sl:
                    log.warning(f"CLOSE-ONLY TRAIL HIT: #{pos.ticket} short closed at {close_price} (SL: {v_sl})")
                    executor.close_position(pos)
                    continue

        # Consolidation exit
        if risk.should_exit_consolidation(m15_rates):
            log.info(f"Consolidation detected -- closing #{pos.ticket}")
            executor.close_position(pos)
            
    if state_changed:
        try:
            import json
            import os as _os
            _vsl_path = _os.path.join(resilience._LOGS, "virtual_sl.json")
            with open(_vsl_path, "w") as f:
                json.dump(virtual_sls, f)
        except Exception as e:
            log.error(f"Failed to save virtual SL state: {e}")


if __name__ == "__main__":
    run()
