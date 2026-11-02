"""Everything that turns a signal into an order, and an order into a record.

Pulled out of main_loop.py on 2026-11-02: the half of the split that was held
back on 2026-11-01 rather than ridden along with a data correction (see
research/AUDIT_2026-11-01.md section 8). main_loop is the scan loop now -- it
decides when to look -- and this module decides whether an order may be sent,
sends it, and records what came back. Nothing about that decision changed in
the move: the bodies are the same code, and the config fingerprint is unchanged.

What lives here:
  - the daily-trend gate: ENABLE_D1_GATE, compute_d1_bias(), _d1_bias_allows(),
    _override_may_apply()
  - the entry path: collect_actionable_signals() gathers what this scan may
    act on, execute_best_signal() applies the Highlander rule to pick one, and
    _execute_signal() sends it -- or refuses it, with every refusal in the order
    the incidents put them in
  - the exit path: _manage_open_positions(), _close_all_positions()
  - what happened afterwards: _record_closed_trades(), _check_vi3_tripwire()
  - the reversal cooldown: _leg_in_cooldown(), _COOLDOWN_FILE

bind() hands over the terminal handle, the symbol and the Atlas switch;
main_loop calls it at import time, and tests/test_module_binding.py checks that
it stays called. Nothing here imports main_loop, so the dependency runs one way.
"""
from __future__ import annotations

import logging
import os
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import numpy as np

from src.atlas import OrderRequest
from src.core import conviction
from src.core import atlas_bridge, market_hours, ops, resilience, risk_rules, scope, trade_alerts, trade_log
from src.core.atlas_bridge import _atlas_account_info
from src.core.execution_handler import FIXED_LOT_SIZE
from src.core.live_status import _alert_foreign_exposure
from src.strategies.portfolio_atlas import PORTFOLIO as PORTFOLIO_ATLAS
from src.strategies.portfolio_v6 import PORTFOLIO as PORTFOLIO_V6

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

mt5: Any = None          # set by main_loop at import time, via bind()
SYMBOL = ""              # set by main_loop at import time, via bind()
ATLAS_MODE = False       # set by main_loop at import time, via bind()

# D1 EMA20 direction gate -- ON. Reversed 2026-09-06 (HYP-064) after August 2026
# simulation proved that trading FVG strategies without trend filtering in a
# high-volatility environment causes extreme drawdowns. The gate flawlessly
# filtered out toxic counter-trend setups in August, turning a -79% maxDD failure
# into a +$44 profit (PF 1.40).
#
# This module owns the switch: the bias computation and the gate function below
# both read it here, and so does SystemConfig.from_live(), so it is one value
# with one home. main_loop deliberately does NOT re-export it -- a re-exported
# copy is exactly what a test patches to no effect.
ENABLE_D1_GATE = True

# P0-3: Global dedup set for (magic, bar_time, direction) to prevent duplicate fills
EXECUTED_ORDERS_DEDUP: set = set()

_TRANSIENT_BLOCK = {"flag": False}     # set by _execute_signal when the block is momentary (spread blip)
_SPREAD_RETRIES: dict = {}             # (strategy, candle) -> retries used

_COOLDOWN_FILE = os.path.join(resilience._LOGS, "cooldown.json")


def bind(mt5_module: Any, symbol: str, atlas_mode: bool) -> None:
    """main_loop hands over its terminal handle, symbol and Atlas switch.

    Called at main_loop import time. All three are fixed for the life of the
    process -- the symbol and the mode come from the environment, the handle is
    the one module-level MetaTrader5 import -- so they are passed once here
    rather than threaded through every call.
    """
    global mt5, SYMBOL, ATLAS_MODE
    mt5 = mt5_module
    SYMBOL = symbol
    ATLAS_MODE = bool(atlas_mode)


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


def compute_d1_bias(d1_rates_macro) -> Optional[str]:
    """The daily trend the entry gate reads, or None when there is not one.

    None means "no bias", which with the gate ON blocks every new entry
    (_d1_bias_allows fails closed). Lifted out of the scan loop unchanged on
    2026-11-02: same bars, same closed-bar index, same override rule. The
    caller still fetches the bars, so this stays testable without a terminal.
    """
    d1_bias = None
    if ENABLE_D1_GATE:
        if d1_rates_macro is not None and len(d1_rates_macro) >= 21:
            # get_d1_rates() uses copy_rates_from_pos(..., 0, n), whose
            # index 0 (and therefore [-1]) is today's still-forming D1
            # candle, not the last closed one. Every other bias/signal
            # check reads the closed bar at [-2] (the scan loop's
            # signal_candle); this gate previously read
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
    return d1_bias


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


def collect_actionable_signals(strategies, m15_rates, m5_rates, d1_bias, last_fired_candle,
                               signal_candle, session_name, is_london) -> list:
    """Every signal this scan may act on, as (strategy, signal) pairs.

    The per-candle dedup, the daily-trend gate and the reversal cooldown all
    decide here; a signal that survives them either goes on the list or, outside
    London, is queued on its strategy for confirmation next candle. Lifted out
    of the scan loop unchanged on 2026-11-02 -- `last_fired_candle` is read, not
    written, exactly as before, and the caller still owns it.
    """
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

    return actionable_signals


def execute_best_signal(actionable_signals, last_fired_candle, signal_candle, m15_rates,
                        fetcher, risk, executor, session_mult, session_name,
                        executed_orders_dedup) -> None:
    """HIGHLANDER RULE: at most one order per scan, the highest-conviction one.

    Lifted out of the scan loop unchanged on 2026-11-02, including the two
    things that are easy to get wrong: `last_fired_candle` is mutated in place
    (the caller holds the same dict), and a signal blocked only by a momentary
    spread blip does NOT mark the candle fired, so the next scan retries it.
    """
    if actionable_signals:
        # One order per scan. The ranking lives in src/core/conviction.py, which
        # the backtest engine reads too -- it used to be a separate table on each
        # side, and neither listed the legs that actually trade (2026-11-02).
        (best_strategy, best_signal), _losers = conviction.pick(actionable_signals)
        actionable_signals = [(best_strategy, best_signal)] + _losers

        if _losers:
            log.info(f"HIGHLANDER: {len(actionable_signals)} signals fired. "
                     f"Selected {best_strategy.name} (rank {conviction.rank(best_strategy.name)}) "
                     f"over {', '.join(s.name for s, _ in _losers)}.")

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
    # ATR from CLOSED bars only (2026-11-01): copy_rates_from_pos(0) ends with the bar that just opened, whose
    # few seconds of range shrank the ATR 5-9% vs the backtest (RESULT_StopRobustness_2026-11-01).
    closed_m15 = m15_rates[:-1] if m15_rates is not None and len(m15_rates) > 1 else m15_rates
    stops = risk.calculate_atr_stops(price, signal.is_buy, closed_m15, sl_mult, tp_mult)
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
    if ATLAS_MODE and atlas_bridge.RUNTIME.get("engine") and atlas_bridge.RUNTIME.get("state"):
        try:
            _acct_at = mt5.account_info()
            if _acct_at is not None:
                _ai_at = _atlas_account_info(_acct_at)
                _atr_val = risk.get_latest_atr(closed_m15) or 0.0
                _stop_risk = float(FIXED_LOT_SIZE * 100.0 * _atr_val * (getattr(strategy, "sl_atr_mult", 2.0) or 2.0))
                _margin_req = float(FIXED_LOT_SIZE * price * 100.0 / 50.0)  # 1:50 leverage
                _ord = OrderRequest(
                    symbol=SYMBOL, stop_risk_usd=_stop_risk,
                    margin_required=_margin_req, volume=FIXED_LOT_SIZE,
                    side="buy" if signal.is_buy else "sell")
                _news = atlas_bridge.RUNTIME["monitor"].get_news_events() if atlas_bridge.RUNTIME.get("monitor") else None
                _decision = atlas_bridge.RUNTIME["engine"].check_order(
                    _ord, _ai_at, atlas_bridge.RUNTIME["state"], datetime.now(timezone.utc), _news)
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
    return result


def _manage_open_positions(fetcher, risk, executor):
    """Run trailing stop logic and consolidation exit checks (own positions only)."""
    positions = fetcher.get_own_positions()
    trade_alerts.maybe_floating_update(positions)
    if not positions:
        return

    m15_rates = fetcher.get_m15_rates(20)
    if m15_rates is None:
        return

    curr_atr = risk.get_latest_atr(m15_rates)
    if curr_atr is None:
        return
        
    for pos in positions:
        # Consolidation exit
        if risk.should_exit_consolidation(m15_rates):
            log.info(f"Consolidation detected -- closing #{pos.ticket}")
            executor.close_position(pos)


def _close_all_positions(fetcher, executor, reason: str, severity: str | None = "CRITICAL") -> None:
    """Flatten every open position on the symbol. severity=None: the caller sends its own message."""
    from src.core import alerts
    if severity == alerts.CRITICAL:
        alerts.send("Kill switch: closing all trades", alerts.CRITICAL, context={"reason": reason},
                    action="The bot stays stopped while the STOP file exists. Delete it, then restart the bot.")
    elif severity:
        alerts.send(f"Closing all trades: {reason}", severity)
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
            alerts.send(f"Could not close trade #{pos.ticket}", alerts.CRITICAL, context={"reason": reason},
                        action="Close it by hand in MT5 now.")


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
            from src.core import trade_alerts
            trade_alerts.closed(ticket, deals, pl, strat_name)
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
            alerts.send(f"Last 30 trades: profit factor {pf:.2f}", alerts.WARN,
                        context={"meaning": "the strategies are losing more than they win lately"},
                        action="Trading continues. Worth a review if it stays below 0.8.")
            # Kill switch disabled
        elif pf < 1.0:
            msg = f"VI.3 TRIPWIRE WARN: Rolling 30-trade PF is {pf:.2f} (<1.0)."
            log.warning(msg)
            from src.core import alerts
            alerts.send(f"Last 30 trades: profit factor {pf:.2f} (below 1)", alerts.INFO)
    except Exception as e:
        log.warning(f"Could not check VI.3 tripwire: {e}")
