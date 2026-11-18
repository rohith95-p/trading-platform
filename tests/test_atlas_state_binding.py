"""Established account risk history must never restart with looser invented anchors."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from scripts.reconcile_atlas_state import prepare_reconciliation
from src.atlas import AtlasState
from src.core import atlas_bridge as bridge, order_flow, main_loop


@pytest.fixture
def identity():
    return SimpleNamespace(login=123, server="dedicated-demo", balance=5000., equity=5000., margin=0.)


@pytest.fixture
def binding(identity):
    return bridge.account_binding(identity, "evaluation", SimpleNamespace(rules={"test": {"value": 1}}))


@pytest.fixture
def state(binding):
    raw = AtlasState.new(5000., datetime.now(timezone.utc)).to_json()
    raw.update(peak_equity=5300., day_high_equity=5200., day_ref_equity=5100., protector_strikes=2)
    return bridge.bind_reconciled_state(raw, binding, {"reviewed_history": "authoritative test anchors"})


def test_bound_roundtrip_preserves_every_risk_anchor(state, binding, identity):
    bridge._save_atlas_state(state)
    restored = bridge._load_atlas_state("evaluation", binding=binding)
    assert restored.to_json() == state.to_json()
    bridge.require_persistence_ready(restored, identity)
    assert json.loads(Path(bridge.ATLAS_STATE_FILE).read_text())["binding"]["initial_balance"] == 5000.


@pytest.mark.parametrize("change", ["login", "server", "program", "phase", "rules_sha256"])
def test_saved_state_cannot_be_adopted_by_another_identity(state, binding, change):
    bridge._save_atlas_state(state)
    changed = dict(binding)
    changed[change] = "different"
    with pytest.raises(bridge.AtlasStateError, match="binding"):
        bridge._load_atlas_state("evaluation", binding=changed)


def test_readable_legacy_state_requires_explicit_migration(state, binding):
    Path(bridge.ATLAS_STATE_FILE).write_text(json.dumps(state.to_json()))
    with pytest.raises(bridge.AtlasStateError, match="unbound|reconciliation"):
        bridge._load_atlas_state("evaluation", binding=binding)


@pytest.mark.parametrize("field,value", [("protector_strikes", -1), ("protector_strikes", 1.5),
                                         ("day_high_equity", float("nan")), ("peak_equity", 4999.),
                                         ("day_start_balance", 0), ("cycle_day_profits", {"2026-11-02": float("inf")})])
def test_corrupted_numeric_history_cannot_load(state, binding, field, value):
    bridge._save_atlas_state(state)
    path = Path(bridge.ATLAS_STATE_FILE)
    document = json.loads(path.read_text())
    document["state"][field] = value
    path.write_text(json.dumps(document))
    with pytest.raises(bridge.AtlasStateError):
        bridge._load_atlas_state("evaluation", binding=binding)


def test_failed_durable_save_disarms_orders_and_retains_pending_history(state, binding, identity, monkeypatch):
    bridge._save_atlas_state(state)
    state.peak_equity = 5400.
    monkeypatch.setattr(bridge.os, "replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(bridge.AtlasStateError, match="durably saved"):
        bridge._save_atlas_state(state)
    with pytest.raises(bridge.AtlasStateError, match="durably saved"):
        bridge.require_persistence_ready(state, identity)
    with pytest.raises(bridge.AtlasStateError, match="Interrupted"):
        bridge._load_atlas_state("evaluation", binding=binding)
    assert Path(bridge.ATLAS_STATE_FILE + ".tmp").exists()


def test_restart_refusal_does_not_start_monitor_or_invent_new_state(identity, monkeypatch):
    monitor = Mock()
    monkeypatch.setattr(bridge, "AtlasMCPMonitor", monitor)
    with pytest.raises(bridge.AtlasStateError):
        bridge._init_atlas(5000., 5000., account=identity)
    monitor.assert_not_called()
    assert not Path(bridge.ATLAS_STATE_FILE).exists()


def test_runtime_account_switch_disarms_state(state, identity):
    bridge._save_atlas_state(state)
    with pytest.raises(bridge.AtlasStateError, match="identity"):
        bridge.require_persistence_ready(state, SimpleNamespace(login=456, server=identity.server))
    assert state._atlas_persistence_ready is False


def test_offline_migration_preserves_original_and_does_not_install(state, binding, tmp_path):
    source, reviewed, output = [tmp_path / name for name in ("legacy.json", "reviewed.json", "prepared.json")]
    original = json.dumps(state.to_json())
    source.write_text(original)
    reviewed.write_text(original)
    prepare_reconciliation(source=source, reviewed=reviewed, output=output, binding=binding,
                           note="Checked authoritative dashboard and complete account history")
    assert source.read_text() == original
    assert not Path(bridge.ATLAS_STATE_FILE).exists()
    document = json.loads(output.read_text())
    assert document["state"] == state.to_json()
    assert document["reconciliation"]["source_status"] == "readable_source_preserved"


@pytest.mark.parametrize("field,value", [("peak_equity", 5200.), ("protector_strikes", 1), ("initial_balance", 4500.)])
def test_migration_cannot_loosen_recorded_anchors(state, binding, tmp_path, field, value):
    source, reviewed = tmp_path / "legacy.json", tmp_path / "reviewed.json"
    source.write_text(json.dumps(state.to_json()))
    raw = state.to_json()
    raw[field] = value
    reviewed.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        prepare_reconciliation(source=source, reviewed=reviewed, output=tmp_path / "prepared.json", binding=binding,
                               note="Checked complete authoritative account history")


def test_missing_history_needs_explicit_recovery_and_never_overwrites_runtime(state, binding, tmp_path):
    reviewed = tmp_path / "reviewed.json"
    reviewed.write_text(json.dumps(state.to_json()))
    kwargs = dict(source=tmp_path / "missing.json", reviewed=reviewed, output=tmp_path / "prepared.json",
                  binding=binding, note="Dashboard risk anchors and complete history reviewed")
    with pytest.raises(ValueError, match="recover-unreadable"):
        prepare_reconciliation(**kwargs)
    prepare_reconciliation(**kwargs, recover_unreadable=True)
    kwargs["output"] = Path(bridge.ATLAS_STATE_FILE)
    with pytest.raises(ValueError, match="runtime"):
        prepare_reconciliation(**kwargs, recover_unreadable=True)


@pytest.mark.parametrize("mode", ["missing_runtime", "failed_save", "switched_account", "unknown_account", "healthy_control"])
def test_order_path_refuses_untrusted_persistence(mode, state, identity, monkeypatch):
    monkeypatch.setattr(order_flow, "ATLAS_MODE", True)
    monkeypatch.setattr(order_flow.ops, "measure_only", lambda: False)
    monkeypatch.setattr(order_flow.scope, "block_on_foreign_enabled", lambda: False)
    monkeypatch.setattr(order_flow.risk_rules, "evaluate", lambda **kwargs: (SimpleNamespace(allow_new_entries=True), object()))
    monkeypatch.setattr(order_flow.risk_rules, "save_state", lambda *args: None)
    monkeypatch.setattr(order_flow.market_hours, "allow_new_entry", lambda: (True, ""))
    bridge._save_atlas_state(state)
    if mode == "failed_save":
        state._atlas_persistence_ready = False
    account = identity
    if mode == "switched_account":
        account = SimpleNamespace(**vars(identity))
        account.login = 456
    if mode == "unknown_account":
        account = None
    monkeypatch.setattr(order_flow.mt5, "account_info", lambda: account)
    engine = Mock()
    engine.check_order.return_value = SimpleNamespace(allow=False, reasons=["test_final_gate"])
    runtime = {} if mode == "missing_runtime" else {"engine": engine, "state": state}
    monkeypatch.setattr(bridge, "RUNTIME", runtime)
    rates = np.zeros(3, dtype=[("time", "i8")])
    rates["time"] = [1794000000, 1794000900, 1794001800]
    signal = SimpleNamespace(direction=0, is_buy=True, direction_str="BUY", strategy_name="TEST", magic=5001)
    risk = Mock()
    risk.calculate_atr_stops.return_value = SimpleNamespace(sl=4900., tp=5200., atr=10.)
    risk.get_latest_atr.return_value = 10.
    fetcher = Mock()
    fetcher.get_tick.return_value = SimpleNamespace(ask=5000., bid=4999.)
    executor = Mock()
    executor.can_open_new_position.return_value = True
    assert order_flow._execute_signal(signal, rates, fetcher, risk, executor, 1., "NY", executed_orders_dedup=set()) is None
    executor.send_order.assert_not_called()
    if mode == "healthy_control":
        engine.check_order.assert_called_once()
    else:
        engine.check_order.assert_not_called()



@pytest.mark.parametrize("field,value", [
    ("peak_equity", float("nan")), ("day_high_equity", None),
    ("protector_strikes", 1.5), ("protector_strikes", -1),
    ("cycle_day_profits", {"2026-11-01": float("inf")}),
    ("last_trade_ts", "2026-11-01T12:00:00"),
])
def test_invalid_history_fields_refuse_before_persistence(state, binding, field, value):
    raw = state.to_json()
    raw[field] = value
    with pytest.raises(bridge.AtlasStateError):
        bridge.bind_reconciled_state(raw, binding, {"reviewed_history": "reviewed"})


@pytest.mark.parametrize("key,value", [
    ("login", 456), ("server", "wrong"), ("program", "other_program"),
    ("phase", "funded"), ("rules_sha256", "f" * 64),
])
def test_persisted_binding_mismatch_fails_closed(state, binding, key, value):
    bridge._save_atlas_state(state)
    expected = dict(binding)
    expected[key] = value
    with pytest.raises(bridge.AtlasStateError):
        bridge._load_atlas_state("evaluation", binding=expected)


def test_valid_account_path_restarts_preserve_risk_floor_strikes_and_profit_days(identity, monkeypatch):
    from src.atlas import load_rules, AtlasRuleEngine, AccountInfo
    rules = load_rules(allow_unverified=bridge.ALLOW_UNVERIFIED)
    binding = bridge.account_binding(identity, "evaluation", rules)
    now = datetime.now(timezone.utc)
    raw = AtlasState.new(5000., now).to_json()
    raw["protector_strikes"] = 2
    state = bridge.bind_reconciled_state(raw, binding, {"reviewed_history": "Authoritative original account anchors reviewed"})
    engine = AtlasRuleEngine(rules)
    engine.update_state(AccountInfo(balance=5100., equity=5400., margin=0., free_margin=5100.), state, now)
    state.cycle_day_profits[now.date()] = 2.0
    bridge._save_atlas_state(state)
    floor, daily = engine.trailing_floor(state), engine.daily_floor(state)
    monitor = Mock()
    monkeypatch.setattr(bridge, "AtlasMCPMonitor", Mock(return_value=monitor))
    restored_engine, restored, _ = bridge._init_atlas(5100., 5200., account=identity)
    assert restored.initial_balance == 5000.
    assert restored.peak_equity == 5400.
    assert restored.protector_strikes == 2
    assert restored.cycle_day_profits[now.date()] == 2.0
    assert restored_engine.trailing_floor(restored) == floor
    assert restored_engine.daily_floor(restored) == daily
    monitor.start.assert_called_once()



def test_validation_failure_also_disarms_and_latches(state):
    from src.core import ops
    bridge._save_atlas_state(state)
    state.protector_strikes = -1
    with pytest.raises(bridge.AtlasStateError):
        bridge._save_atlas_state(state)
    assert state._atlas_persistence_ready is False
    assert ops.halt_status()["source"] == "atlas_state_persistence"


def test_offline_write_failure_does_not_touch_live_halt(state, binding, tmp_path, monkeypatch):
    from src.core import ops
    monkeypatch.setattr(bridge.os, "replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(bridge.AtlasStateError):
        bridge._save_atlas_state(state, path=tmp_path / "offline.json")
    assert ops.halt_status() is None
