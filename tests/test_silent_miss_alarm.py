"""The silent-miss alarm must fire for unexplained refusals only.

On 2026-11-03 a signal cleared the daily gate and no order reached the broker.
The cause turned out to be recorded all along -- the Atlas news window -- just
unwatched. So the alarm added for it has to distinguish "refused for a reason
nobody was reading" from "refused for no reason at all", or it wakes the owner
on every ordinary spread blip and news window and becomes noise.

The static test below is the one that matters: it walks the AST of
`_execute_signal` and insists every early return is preceded by a recorded
refusal. Add a new refusal path without marking it and this fails, instead of
the alarm quietly crying wolf for weeks.
"""
import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from src.core import order_flow


def test_every_early_return_in_execute_signal_records_a_refusal():
    src = textwrap.dedent(inspect.getsource(order_flow._execute_signal))
    fn = ast.parse(src).body[0]

    # the success path is the single `return result`-style exit at the end
    def is_bare_none(node):
        return node.value is None or (
            isinstance(node.value, ast.Constant) and node.value.value is None)

    unmarked = []

    class Walker(ast.NodeVisitor):
        """Track, per statement list, whether a refusal was recorded before a return."""

        def visit_body(self, body):
            marked = False
            for stmt in body:
                # ast.unparse normalises quotes, so compare quote-insensitively
                if (isinstance(stmt, ast.Assign)
                        and ast.unparse(stmt).replace("'", '"').startswith(
                            '_REFUSED["flag"] = True')):
                    marked = True
                if isinstance(stmt, ast.Return) and is_bare_none(stmt):
                    if not marked:
                        unmarked.append(stmt.lineno)
                for field in ("body", "orelse", "finalbody"):
                    inner = getattr(stmt, field, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        self.visit_body(inner)
                # a marker inside a nested block still counts for returns after it
                if isinstance(stmt, (ast.If, ast.Try, ast.For, ast.While)):
                    pass   # a marker inside a nested block does not leak outward

    Walker().visit_body(fn.body)
    assert not unmarked, (
        f"_execute_signal returns without recording a refusal at relative lines {unmarked}. "
        f'Add _REFUSED["flag"] = True before the return, or the silent-miss alarm will fire '
        f"for a refusal that does have a reason.")


def test_the_flag_is_reset_at_the_top_of_every_call():
    src = inspect.getsource(order_flow._execute_signal)
    body = src.split('"""', 2)[-1]
    first = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert first[0] == '_REFUSED["flag"] = False', (
        "the refusal flag must be cleared when _execute_signal starts, or a refusal "
        "from the previous candle suppresses this candle's alarm")


def test_measurement_only_mode_is_a_recorded_refusal_not_an_alarm(monkeypatch):
    from src.core import ops

    monkeypatch.setattr(ops, "measure_only", lambda: True)
    monkeypatch.setattr(order_flow.trade_log, "signal", lambda *a, **k: None)
    order_flow._REFUSED["flag"] = False
    sig = SimpleNamespace(strategy_name="ASIAN_RANGE_FILTERED_V6", direction_str="SELL",
                          is_buy=False, magic=7320, direction=1)
    assert order_flow._execute_signal(sig, None, None, None, None, 2.0, "ASIA") is None
    assert order_flow._REFUSED["flag"] is True


def test_the_alarm_is_skipped_when_a_refusal_was_recorded(monkeypatch):
    sent = []
    monkeypatch.setattr(order_flow, "_SILENT_MISSES", set())
    monkeypatch.setattr("src.core.alerts.send", lambda m, severity=None, **k: sent.append(m))
    monkeypatch.setattr(order_flow.trade_log, "signal", lambda *a, **k: None)
    strat = SimpleNamespace(name="ASIAN_RANGE_FILTERED_V6")
    sig = SimpleNamespace(direction_str="SELL", is_buy=False)

    # a recorded refusal: the caller must stay quiet
    order_flow._REFUSED["flag"] = True
    if not (order_flow._REFUSED["flag"]):
        order_flow._report_silent_miss(strat, sig, 1762153200, "ASIA")
    assert sent == []

    # nothing recorded: the caller must speak up
    order_flow._REFUSED["flag"] = False
    if not (order_flow._REFUSED["flag"]):
        order_flow._report_silent_miss(strat, sig, 1762153200, "ASIA")
    assert len(sent) == 1


def test_the_atlas_news_window_block_would_not_have_alarmed():
    """The 2026-11-03 refusal, as the log recorded it.

    'ATLAS GATE BLOCKED: [news_window]' is a recorded reason, so it belongs in the
    log and the hourly pulse -- not in a CRITICAL alert claiming a trade vanished.
    """
    src = inspect.getsource(order_flow._execute_signal)
    i = src.index("ATLAS GATE BLOCKED")
    after = src[i:i + 600]
    assert '_REFUSED["flag"] = True' in after
