"""Exercise actual display/gate expressions without running legacy backtests."""
import ast
import json
from pathlib import Path

import numpy as np
import pytest

from src.backtesting.report import format_metric, format_report, metric_at_least
from tests.test_reporting_math import report

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pnls,status", [([], "undefined_no_trades"), ([1.]*5, "unbounded_no_observed_losses")])
def test_normal_report_no_trade_no_loss_presentation_preserves_status(pnls, status):
    result = report(pnls)
    text = format_report(result)
    assert status in text
    assert "n/a" in text
    assert result["stats"]["profit_factor"] is None
    assert result["stats"]["profit_factor_status"] == status
    assert "nan" not in text.lower().split()
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value,shown,passes", [(None, "n/a", False), (0., "0.000", False),
                                              (1.4, "1.400", True), (float("inf"), "n/a", False)])
def test_nullable_ratio_presentation_and_screening_never_invents_a_value(value, shown, passes):
    assert format_metric(value) == shown
    assert metric_at_least(value, 1.3) == passes


@pytest.mark.parametrize("filename", ["atlas_filter_study.py", "momentum_portfolio_2026_10_25.py",
                                     "atlas_backtest_2026_10_25.py", "donchian_sweep_2026_10_25.py"])
@pytest.mark.parametrize("pnls", [[], [1.]*5])
def test_actual_legacy_output_expressions_accept_undefined_pf(filename, pnls):
    # Several legacy scripts run research at module import. Compile only their
    # actual changed string-format expressions, with normal report output as data.
    tree = ast.parse((ROOT/"scripts/research"/filename).read_text())
    stats = report(pnls)["stats"]
    scope = dict(format_metric=format_metric, d=stats, day={}, pf=stats["profit_factor"],
                 split_name="DEV", n_trades=stats["trades"], n=stats["trades"],
                 win_rate=stats["win_rate"], wr=stats["win_rate"], net=stats["net_pl"],
                 bal=np.array([100.+stats["net_pl"]]), max_dd=0., dd_pct=0., losses=[], status="FAIL",
                 r={"n": stats["trades"], "pf": stats["profit_factor"], "wr": stats["win_rate"],
                    "net": stats["net_pl"], "max_dd_pct": 0., "worst_day_pct": 0.,
                    "profit_days": 0, "best_day_share": 0.},
                 atlas_dd_ok="PASS", atlas_daily_ok="PASS", target_str="NOT HIT")
    expressions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and "format_metric(" in ast.unparse(node):
            expressions.append(node)
        elif (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)
              and isinstance(node.left, ast.Constant) and "PF=" in str(node.left.value)
              and "format_metric(" in ast.unparse(node)):
            expressions.append(node)
    assert expressions, "Missing expected caller output path"
    for expression in expressions:
        text = eval(compile(ast.Expression(expression), filename, "eval"), scope)
        assert "n/a" in text


@pytest.mark.parametrize("split", ["DEV", "VALIDATE", "HOLDOUT"])
def test_actual_legacy_momentum_gate_fails_undefined_pf_without_comparison_error(split):
    source = (ROOT/"scripts/research/momentum_portfolio_2026_10_25.py").read_text()
    tree = ast.parse(source)
    block = None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for i, statement in enumerate(body):
            if (isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "passed"
                                                         for t in statement.targets)):
                selected = []
                for later in body[i:]:
                    selected.append(later)
                    if (isinstance(later, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "status"
                                                             for t in later.targets)):
                        block = selected
                        break
    assert block is not None
    for pf, expected in ((None, "FAIL"), (1.4, "PASS")):
        scope = dict(metric_at_least=metric_at_least, split_name=split, pf=pf, dd_pct=0., n_trades=20)
        exec(compile(ast.Module(body=block, type_ignores=[]), "legacy_gate_only", "exec"), scope)
        assert scope["status"] == expected


def test_all_strategy_record_keeps_null_and_its_reason():
    tree = ast.parse((ROOT/"scripts/research/all_strategies_2026.py").read_text())
    update = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and any(keyword.arg == "pf_status" for keyword in node.keywords))
    stats = report([1.]*5)["stats"]
    values = {keyword.arg: eval(compile(ast.Expression(keyword.value), "record_field", "eval"),
                                {"d": stats, "monthly": {}}) for keyword in update.keywords}
    assert values["pf"] is None
    assert values["pf_status"] == "unbounded_no_observed_losses"
    json.dumps(values, allow_nan=False)
