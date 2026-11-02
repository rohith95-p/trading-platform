"""The modules split out of main_loop are bound at import, and stay bound.

`live_status` and `order_flow` hold no terminal handle of their own: main_loop
hands over its MetaTrader5 handle, the symbol and (for order_flow) the Atlas
switch through a `bind()` call at import time. An import-order change that
skipped that call would leave `mt5` as None, and the failure would be quiet --
every order attempt dies inside an `except Exception` that logs at debug level,
so the bot would scan, log, and never trade. These tests fail loudly instead.

They also pin which names main_loop may re-export. A function or a mutable
container can be re-exported, because the re-export is the same object. A plain
value cannot: the copy and the original drift the moment either is patched, and
a test pointing at the copy passes while the live code reads the original. That
exact trap cost an hour on 2026-11-01.
"""
import inspect

from src.core import atlas_bridge, live_status, main_loop, order_flow


def test_order_flow_is_bound_by_importing_main_loop():
    assert order_flow.mt5 is main_loop.mt5
    assert order_flow.SYMBOL == main_loop.SYMBOL != ""
    assert order_flow.ATLAS_MODE == main_loop.ATLAS_MODE


def test_live_status_is_bound_by_importing_main_loop():
    assert live_status.mt5 is main_loop.mt5
    assert live_status.SYMBOL == main_loop.SYMBOL != ""


def test_both_bind_calls_run_at_import_and_not_inside_a_function():
    """A bind() call that drifts into startup() or run() leaves every other
    caller -- tests, scripts, the watchdog -- importing an unbound module."""
    at_module_level = [ln for ln in inspect.getsource(main_loop).split("\n")
                       if ln.startswith(("order_flow.bind(", "live_status.bind("))]
    assert at_module_level == ["live_status.bind(mt5, SYMBOL)",
                               "order_flow.bind(mt5, SYMBOL, ATLAS_MODE)"]


def test_the_re_exported_containers_are_the_same_object():
    assert main_loop.EXECUTED_ORDERS_DEDUP is order_flow.EXECUTED_ORDERS_DEDUP
    assert main_loop._TRANSIENT_BLOCK is order_flow._TRANSIENT_BLOCK
    assert main_loop._ATLAS_RT is atlas_bridge.RUNTIME


def test_the_moved_functions_are_re_exported_unwrapped():
    for name in ("_calc_ema", "_check_vi3_tripwire", "_close_all_positions",
                 "_d1_bias_allows", "_execute_signal", "_leg_in_cooldown",
                 "_manage_open_positions", "_override_may_apply", "_record_closed_trades"):
        assert getattr(main_loop, name) is getattr(order_flow, name), name


def test_the_plain_values_that_moved_are_not_re_exported():
    """Patch and read these on their owner. main_loop must not offer a copy."""
    assert not hasattr(main_loop, "ENABLE_D1_GATE")
    assert not hasattr(main_loop, "_COOLDOWN_FILE")
    assert order_flow.ENABLE_D1_GATE is True
    assert order_flow._COOLDOWN_FILE.endswith("cooldown.json")
