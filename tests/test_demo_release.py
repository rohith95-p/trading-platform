"""Safety properties for prepared releases and read-only demo diagnostics."""
from pathlib import Path
from types import SimpleNamespace
import json
import zipfile

import pytest

from scripts import demo_release, demo_preflight

SHA = "a" * 40


def archive(tmp_path, members=None):
    file = tmp_path / "source.zip"
    with zipfile.ZipFile(file, "w") as output:
        for name, value in (members or {"src/example.py": "print('example')"}).items():
            output.writestr("trading-platform-" + SHA + "/" + name, value)
    return file


def test_prepare_verifies_pinned_archive_without_touching_live(tmp_path):
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "example.py").write_text("original")
    bundle = archive(tmp_path, {"src/example.py": "new", ".env.local": "SECRET", "logs/state.json": "state"})
    release = demo_release.prepare_archive(root, bundle, SHA, demo_release.sha256(bundle))
    assert (root / "src" / "example.py").read_text() == "original"
    assert (release / "src" / "example.py").read_text() == "new"
    assert not (release / ".env.local").exists()
    assert not (release / "logs").exists()
    assert demo_release.verify_release(release)["activation"] == "NOT_ACTIVATED"
    with pytest.raises(ValueError, match="never overwritten"):
        demo_release.prepare_archive(root, bundle, SHA, demo_release.sha256(bundle))


def test_bad_archive_hash_leaves_no_release(tmp_path):
    bundle = archive(tmp_path)
    with pytest.raises(ValueError, match="mismatch"):
        demo_release.prepare_archive(tmp_path / "project", bundle, SHA, "0" * 64)
    assert not (tmp_path / "project").exists()


@pytest.mark.parametrize("name", ["src/../../escaped.py", "src/..\\..\\escaped.py", "src/C:escape.py"])
def test_archive_path_traversal_rejected_before_extract(tmp_path, name):
    bundle = archive(tmp_path, {name: "bad"})
    with pytest.raises(ValueError, match="Unsafe"):
        demo_release.prepare_archive(tmp_path / "project", bundle, SHA, demo_release.sha256(bundle))
    assert not (tmp_path / "project").exists()


def test_wrong_revision_root_and_short_revision_refused(tmp_path):
    bundle = archive(tmp_path)
    with pytest.raises(ValueError, match="40-character"):
        demo_release.prepare_archive(tmp_path, bundle, "master", demo_release.sha256(bundle))
    with pytest.raises(ValueError, match="pinned"):
        demo_release.prepare_archive(tmp_path, bundle, "b" * 40, demo_release.sha256(bundle))


def test_duplicate_casefolded_member_refused(tmp_path):
    bundle = archive(tmp_path, {"src/Main.py": "one", "src/main.py": "two"})
    with pytest.raises(ValueError, match="case-colliding"):
        demo_release.prepare_archive(tmp_path / "project", bundle, SHA, demo_release.sha256(bundle))


def test_symbolic_link_archive_member_refused(tmp_path):
    file = tmp_path / "link.zip"
    with zipfile.ZipFile(file, "w") as output:
        link = zipfile.ZipInfo("trading-platform-" + SHA + "/src/link")
        link.create_system = 3
        link.external_attr = (0o120777 << 16)
        output.writestr(link, "../../outside")
    with pytest.raises(ValueError, match="symlinks"):
        demo_release.prepare_archive(tmp_path / "project", file, SHA, demo_release.sha256(file))


@pytest.mark.parametrize("change", ["modify", "extra", "missing"])
def test_release_verifier_detects_file_set_or_content_tampering(tmp_path, change):
    bundle = archive(tmp_path)
    release = demo_release.prepare_archive(tmp_path / "project", bundle, SHA, demo_release.sha256(bundle))
    source = release / "src" / "example.py"
    if change == "modify":
        source.write_text("tampered")
    elif change == "missing":
        source.unlink()
    else:
        (release / "extra.txt").write_text("extra")
    with pytest.raises(ValueError):
        demo_release.verify_release(release)


def test_code_rollback_snapshot_preserves_live_state_and_excludes_secrets(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("code")
    (tmp_path / "src" / ".env.token").write_text("SECRET")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "atlas_state.json").write_text("account history")
    release = demo_release.snapshot_current(tmp_path, "before_demo")
    manifest = demo_release.verify_release(release)
    assert manifest["kind"] == "local_code_rollback"
    assert set(manifest["files"]) == {"src/main.py"}
    assert (tmp_path / "logs" / "atlas_state.json").read_text() == "account history"


def test_owned_process_plan_does_not_match_unrelated_python_or_similar_names(tmp_path):
    root = tmp_path / "Project With Spaces"
    executable = str(root / "venv" / "Scripts" / "python.exe")
    records = [
        {"ProcessId": 11, "CommandLine": f'"{executable}" -m src.core.main_loop'},
        {"ProcessId": 12, "CommandLine": f'"{executable}" "{root / "scripts" / "watchdog.py"}"'},
        {"ProcessId": 13, "CommandLine": f'"{executable}" -m scripts.research.other'},
        {"ProcessId": 14, "CommandLine": '"C:/Other/python.exe" -m src.core.main_loop'},
        {"ProcessId": 15, "CommandLine": f'"{executable}" -m src.core.main_loop_extra'},
        {"ProcessId": 16, "CommandLine": f'"{executable}" "{tmp_path / "Other" / "scripts" / "watchdog.py"}"'},
        {"ProcessId": 17, "CommandLine": None},
    ]
    assert demo_release.owned_processes(root, records) == [
        {"pid": 11, "role": "trading_loop"}, {"pid": 12, "role": "watchdog"},
    ]


def terminal(**account_changes):
    account = dict(login=123, server="Demo-Test", trade_mode=0, margin_mode=2)
    account.update(account_changes)
    called = []
    obj = SimpleNamespace(
        initialize=lambda: called.append("initialize") or True,
        shutdown=lambda: called.append("shutdown"),
        account_info=lambda: SimpleNamespace(**account),
        terminal_info=lambda: SimpleNamespace(connected=True),
        symbol_info=lambda symbol: SimpleNamespace(point=.001, trade_contract_size=100., volume_min=.01, volume_step=.01),
        positions_get=lambda: (), orders_get=lambda: (),
        order_send=lambda request: pytest.fail("Order API must never be called"),
    )
    return obj, called


def test_dedicated_demo_read_only_diagnostic_has_no_orders_or_identity_output():
    fake, called = terminal()
    result = demo_preflight.assess(fake, 123, "Demo-Test", "XAUUSDm")
    assert result["status"] == "READ_ONLY_DEMO_IDENTITY_VERIFIED"
    assert result["release_order_enabled"] is False
    assert "123" not in json.dumps(result)
    assert "Demo-Test" not in json.dumps(result)
    assert called == ["initialize", "shutdown"]
    with pytest.raises(PermissionError):
        demo_preflight.ReadOnlyTerminal(fake).order_send({})


@pytest.mark.parametrize("changes,expected", [
    ({"trade_mode": 2}, "account_is_not_verified_demo"),
    ({"trade_mode": None}, "account_is_not_verified_demo"),
    ({"login": 456}, "account_identity_mismatch"),
    ({"server": "Other"}, "account_identity_mismatch"),
    ({"margin_mode": 0}, "hedging_mode_required"),
])
def test_real_unknown_or_wrong_account_cannot_pass(changes, expected):
    fake, called = terminal(**changes)
    result = demo_preflight.assess(fake, 123, "Demo-Test", "XAUUSD")
    assert result["status"] == "REFUSED"
    assert expected in result["reasons"]
    assert called[-1] == "shutdown"


def test_unknown_or_existing_exposure_refuses_demo_release():
    fake, _ = terminal()
    fake.positions_get = lambda: None
    assert "exposure_query_failed" in demo_preflight.assess(fake, 123, "Demo-Test", "XAUUSD")["reasons"]
    fake.positions_get = lambda: (object(),)
    assert "dedicated_empty_demo_required" in demo_preflight.assess(fake, 123, "Demo-Test", "XAUUSD")["reasons"]


def test_presence_inspection_never_initializes_terminal_or_reads_env(tmp_path, monkeypatch):
    (tmp_path / ".env.local").write_text("TOKEN=SHOULD_NOT_APPEAR")
    monkeypatch.setattr(demo_preflight.importlib.util, "find_spec", lambda name: object())
    result = demo_preflight.presence(tmp_path)
    assert result["status"] == "PRESENCE_ONLY_NOT_CONNECTED"
    assert result["local_settings_present"] is True
    assert "SHOULD_NOT_APPEAR" not in json.dumps(result)
    assert result["account_demo_verified"] is False


def test_owned_process_plan_excludes_unrelated_or_ambiguous_processes(tmp_path):
    root = tmp_path / "project with spaces"
    interpreter = root / "venv" / "Scripts" / "python.exe"
    records = [
        {"ProcessId": 1, "CommandLine": f'"{interpreter}" -m src.core.main_loop'},
        {"ProcessId": 2, "CommandLine": f'"{interpreter}" "{root / "scripts" / "watchdog.py"}"'},
        {"ProcessId": 3, "CommandLine": f'"{interpreter}" -m pytest'},
        {"ProcessId": 4, "CommandLine": '"C:\\Other\\python.exe" -m src.core.main_loop'},
        {"ProcessId": 5, "CommandLine": f'"{interpreter}" "{tmp_path / "other" / "scripts" / "watchdog.py"}"'},
        {"ProcessId": 6, "CommandLine": None},
        {"ProcessId": -1, "CommandLine": f'"{interpreter}" -m scripts.watchdog'},
    ]
    assert demo_release.owned_processes(root, records) == [
        {"pid": 1, "role": "trading_loop"}, {"pid": 2, "role": "watchdog"}
    ]


def test_nested_manifest_name_cannot_hide_an_extra_file(tmp_path):
    bundle = archive(tmp_path)
    release = demo_release.prepare_archive(tmp_path / "project", bundle, SHA, demo_release.sha256(bundle))
    (release / "src" / "RELEASE_MANIFEST.json").write_text("hidden extra")
    with pytest.raises(ValueError, match="file set"):
        demo_release.verify_release(release)
