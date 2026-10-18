"""Operational safety: halt latch, measurement-only mode, external heartbeat, supervisor decisions (2026-10-18)."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from src.core import ops


# ------------------------------------------------------------------ halt latch
def test_not_halted_by_default():
    assert ops.halt_status() is None


def test_set_halt_persists_and_keeps_first_cause():
    ops.set_halt("peak drawdown 31%", "risk_rules")
    st = ops.halt_status()
    assert st["reason"] == "peak drawdown 31%" and st["source"] == "risk_rules"
    ops.set_halt("something else", "operator")          # idempotent: first cause is kept
    assert ops.halt_status()["reason"] == "peak drawdown 31%"


def test_corrupt_latch_file_counts_as_halted_fail_closed():
    with open(ops.HALT_FILE, "w") as f:
        f.write("{not json")
    assert ops.halt_status() is not None


def test_clear_requires_a_note_and_archives():
    ops.set_halt("x", "t")
    with pytest.raises(ValueError):
        ops.clear_halt("   ")
    assert ops.halt_status() is not None                 # still halted
    assert ops.clear_halt("reconciled with broker, flat") is True
    assert ops.halt_status() is None
    folder = os.path.dirname(ops.HALT_FILE)
    archived = [n for n in os.listdir(folder) if "cleared_" in n]
    assert len(archived) == 1
    assert json.load(open(os.path.join(folder, archived[0])))["operator_note"].startswith("reconciled")


def test_clear_when_not_halted_returns_false():
    assert ops.clear_halt("nothing to clear") is False


def test_halt_is_read_from_disk_not_process_memory():
    ops.set_halt("persist", "t")
    # a "restart" has no in-memory state: it only has the file, and the file says halted
    assert os.path.exists(ops.HALT_FILE)
    assert ops.halt_status()["reason"] == "persist"


def test_halt_cli():
    from scripts import halt
    assert halt.main(["status"]) == 0
    assert halt.main(["set", "--reason", "manual"]) == 0
    assert halt.main(["status"]) == 2
    assert halt.main(["clear", "--note", " "]) == 1
    assert halt.main(["clear", "--note", "ok after review"]) == 0
    assert halt.main(["status"]) == 0


# ------------------------------------------------------------------ measurement-only
@pytest.mark.parametrize("val,expected", [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("no", False)])
def test_measure_only_env(monkeypatch, val, expected):
    monkeypatch.setenv("ULTRA_MEASURE_ONLY", val)
    assert ops.measure_only() is expected


def test_execute_signal_sends_nothing_in_measure_only(monkeypatch):
    from src.core import main_loop as ml
    monkeypatch.setenv("ULTRA_MEASURE_ONLY", "1")

    class Boom:
        def __getattr__(self, name):
            raise AssertionError(f"{name} must not be touched in measurement-only mode")

    sig = SimpleNamespace(strategy_name="T", direction_str="BUY", is_buy=True, magic=1, direction=0)
    assert ml._execute_signal(sig, None, Boom(), Boom(), Boom(), 1.5, "NY_MORNING") is None


# ------------------------------------------------------------------ status payload
def test_rule_state_precedence(monkeypatch):
    monkeypatch.delenv("ULTRA_MEASURE_ONLY", raising=False)
    assert ops.rule_state() == "NORMAL"
    monkeypatch.setenv("ULTRA_MEASURE_ONLY", "1")
    assert ops.rule_state() == "MEASURE_ONLY"
    assert ops.rule_state(drawdown_shutdown=True) == "DAILY_SHUTDOWN"
    ops.set_halt("x", "t")
    assert ops.rule_state(drawdown_shutdown=True) == "HALT_LATCHED"


def test_build_status_fields_and_rounding():
    p = ops.build_status(account="demo", scan_interval_s=60.123, quote_age_s=0.456, open_positions=1,
                         pending_orders=0, daily_pnl=-0.4219)
    for k in ("bot", "account", "commit", "config_fingerprint", "scan_interval_s", "quote_age_s", "open_positions",
              "pending_orders", "daily_pnl", "rule_state", "measure_only", "ts_utc"):
        assert k in p
    assert p["scan_interval_s"] == 60.1 and p["quote_age_s"] == 0.5 and p["daily_pnl"] == -0.42
    assert p["ts_utc"].endswith("+00:00")


# ------------------------------------------------------------------ external heartbeat
class _Rec(BaseHTTPRequestHandler):
    got = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _Rec.got.append((self.path, json.loads(self.rfile.read(n))))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


def test_push_status_posts_json_to_a_real_local_endpoint(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Rec)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _Rec.got.clear()
    monkeypatch.setenv("ULTRA_HEARTBEAT_URL", f"http://127.0.0.1:{srv.server_address[1]}/ping")
    monkeypatch.setattr(ops, "_last_push", 0.0)
    payload = ops.build_status(account="demo", scan_interval_s=60, quote_age_s=1, open_positions=0,
                               pending_orders=0, daily_pnl=0)
    assert ops.push_status(payload, force=True) is True
    for _ in range(80):
        if _Rec.got:
            break
        time.sleep(0.05)
    srv.shutdown()
    assert _Rec.got and _Rec.got[0][0] == "/ping" and _Rec.got[0][1]["bot"] == "ultra_core"


def test_push_status_is_noop_without_url_and_rate_limited(monkeypatch):
    monkeypatch.delenv("ULTRA_HEARTBEAT_URL", raising=False)
    assert ops.push_status({"rule_state": "NORMAL"}, force=True) is False
    monkeypatch.setenv("ULTRA_HEARTBEAT_URL", "http://127.0.0.1:9/x")
    started = []
    monkeypatch.setattr(ops, "_post", lambda u, p: started.append(u))
    monkeypatch.setattr(ops, "_last_push", 0.0)
    assert ops.push_status({"rule_state": "NORMAL"}) is True
    assert ops.push_status({"rule_state": "NORMAL"}) is False          # within 30 s


def test_halt_state_pings_the_fail_endpoint_for_healthchecks(monkeypatch):
    seen = []

    class Sync:
        def __init__(self, target, args, daemon):
            self.t, self.a = target, args

        def start(self):
            self.t(*self.a)

    monkeypatch.setattr(ops.threading, "Thread", Sync)
    monkeypatch.setattr(ops, "_post", lambda u, p: seen.append(u))
    monkeypatch.setenv("ULTRA_HEARTBEAT_URL", "https://hc-ping.com/abc-123")
    monkeypatch.setattr(ops, "_last_push", 0.0)
    ops.push_status({"rule_state": "HALT_LATCHED"}, force=True)
    ops.push_status({"rule_state": "NORMAL"}, force=True)
    assert seen == ["https://hc-ping.com/abc-123/fail", "https://hc-ping.com/abc-123"]


def test_push_never_raises_on_unreachable_endpoint():
    ops._post("http://127.0.0.1:9/unreachable", {"a": 1})              # must swallow the error


# ------------------------------------------------------------------ supervisor decisions
def test_supervisor_refuses_to_start_under_halt_or_stop():
    from scripts import supervisor as sv
    assert sv.decide_start({"source": "risk_rules", "reason": "x"}, False, [], 1000.0)[0] is False
    assert sv.decide_start(None, True, [], 1000.0) == (False, "STOP file present")
    assert sv.decide_start(None, False, [], 1000.0) == (True, "ok")


def test_supervisor_crash_loop_guard_and_backoff():
    from scripts import supervisor as sv
    now = 10_000.0
    assert sv.decide_start(None, False, [now - 10] * 5, now)[0] is False
    assert sv.decide_start(None, False, [now - 5000] * 9, now)[0] is True         # old crashes do not count
    assert [sv.backoff_seconds(n) for n in (1, 2, 3, 7, 12)] == [5.0, 10.0, 20.0, 300.0, 300.0]


def test_heartbeat_stale_detection(tmp_path):
    from scripts import supervisor as sv
    f = tmp_path / "hb"
    assert sv.heartbeat_stale(str(f), time.time()) is False                       # no file yet
    f.write_text("x")
    assert sv.heartbeat_stale(str(f), time.time()) is False
    assert sv.heartbeat_stale(str(f), time.time() + 301) is True
