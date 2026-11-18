"""Everything between this bot and the Atlas rule engine.

Pulled out of main_loop.py on 2026-11-01. It holds the saved-state file (so a
restart keeps Atlas's real peak and daily reference rather than inventing new
ones), the translation from an MT5 account into the rule engine's AccountInfo,
and the plain-English reading of a breach reason.

`RUNTIME` is the live engine/state/monitor, filled in by main_loop once the
account is known and read by anything that needs the current Atlas floors.
"""
from __future__ import annotations

import hashlib
import json
import math
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from src.atlas import (AccountInfo, AtlasRuleEngine, AtlasState, load_rules)
from src.atlas.mcp_monitor import AtlasMCPMonitor
from src.core import resilience

log = logging.getLogger(__name__)

# Unverified rules the engine must acknowledge to load (see config/atlas_access.json).
ALLOW_UNVERIFIED = ["daily_loss_eod_computation", "ea_approval_required"]

# The live engine, state and news monitor. A dict, not module globals, because
# main_loop fills it in after connecting and other modules read it live.
RUNTIME: dict = {}

ATLAS_STATE_FILE = os.path.join(os.path.dirname(resilience.HEARTBEAT_FILE), "atlas_state.json")

HALT_CLEAR_HELP = ('RDP into the VPS, check MT5, then in PowerShell: cd C:\\projects\\ultra_core; '
                   'venv\\Scripts\\python.exe -m scripts.halt clear --note "checked". '
                   'The watchdog restarts the bot.')

_ATLAS_WORDS = {"daily_loss": "today's loss", "trailing_dd": "total drawdown",
                "protector": "open-trade loss", "margin": "margin use"}


class AtlasStateError(RuntimeError):
    """Account risk history is unavailable/untrusted; no new orders may proceed."""


def account_binding(account, phase: str, rules) -> dict:
    login, server = getattr(account, "login", None), getattr(account, "server", None)
    if isinstance(login, bool) or not isinstance(login, int) or login <= 0:
        raise AtlasStateError("Atlas account identity unavailable")
    if not isinstance(server, str) or not server.strip() or phase not in {"evaluation", "funded"}:
        raise AtlasStateError("Atlas account server or phase unavailable")
    fingerprint = hashlib.sha256(json.dumps(rules.rules, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {"login": login, "server": server, "program": "atlas_access", "phase": phase,
            "rules_sha256": fingerprint}


def _check_binding(binding: dict, *, stored: bool = False) -> None:
    required = {"login", "server", "program", "phase", "rules_sha256"}
    if stored:
        required.add("initial_balance")
    if not isinstance(binding, dict) or set(binding) != required:
        raise AtlasStateError("Complete explicit Atlas account binding required")
    if (isinstance(binding["login"], bool) or not isinstance(binding["login"], int)
            or binding["login"] <= 0 or not isinstance(binding["server"], str)
            or not binding["server"].strip() or binding["program"] != "atlas_access"
            or binding["phase"] not in {"evaluation", "funded"}
            or not isinstance(binding["rules_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", binding["rules_sha256"])):
        raise AtlasStateError("Atlas account identity/phase/rules binding invalid")


def _validated_state(raw: dict) -> AtlasState:
    if not isinstance(raw, dict):
        raise AtlasStateError("Atlas state must be an object")
    if set(AtlasState.new(1.0, datetime.now(timezone.utc)).to_json()) - set(raw):
        raise AtlasStateError("Atlas state fields are incomplete; explicit reconciliation required")
    strikes = raw.get("protector_strikes")
    if isinstance(strikes, bool) or not isinstance(strikes, int) or strikes < 0:
        raise AtlasStateError("Atlas protector strike history invalid")
    try:
        state = AtlasState.from_json(raw)
        if state.phase not in {"evaluation", "funded"}:
            raise ValueError("phase")
        for name in ("initial_balance", "peak_equity", "day_ref_equity", "day_high_equity", "day_start_balance"):
            value = getattr(state, name)
            if isinstance(raw[name], bool) or value is None or not math.isfinite(value) or value <= 0:
                raise ValueError("non-finite/nonpositive equity history")
        if state.peak_equity < max(state.initial_balance, state.day_ref_equity, state.day_high_equity):
            raise ValueError("peak is below recorded equity history")
        if any(not math.isfinite(value) for value in state.cycle_day_profits.values()):
            raise ValueError("non-finite payout history")
        if state.last_trade_ts is not None and state.last_trade_ts.tzinfo is None:
            raise ValueError("trade timestamp lacks timezone")
    except Exception as exc:
        raise AtlasStateError("Atlas state is invalid; explicit reconciliation required") from exc
    return state


def bind_reconciled_state(raw: dict, binding: dict, provenance: dict) -> AtlasState:
    """Offline preparation helper, never an automatic migration/startup path."""
    state = _validated_state(raw)
    _check_binding(binding)
    if binding["phase"] != state.phase:
        raise AtlasStateError("Reconciled identity/phase binding invalid")
    if not isinstance(provenance, dict) or not provenance.get("reviewed_history"):
        raise AtlasStateError("Explicit reviewed-history provenance required")
    state._atlas_binding = dict(binding, initial_balance=state.initial_balance)
    state._atlas_reconciliation = provenance
    state._atlas_persistence_ready = False
    return state


def _init_atlas(balance: float, equity: float, *, account=None) -> tuple:
    """Resume only explicit account-bound history; absent history never resets risk."""
    RUNTIME.clear()
    rules = load_rules(allow_unverified=ALLOW_UNVERIFIED)
    engine = AtlasRuleEngine(rules)
    phase = os.environ.get("ULTRA_ATLAS_PHASE", "evaluation")
    binding = account_binding(account, phase, rules)
    state = _load_atlas_state(phase, binding=binding)
    _save_atlas_state(state)
    monitor = AtlasMCPMonitor(poll_interval=300.0)
    monitor.start()
    return engine, state, monitor


def _load_atlas_state(phase: str, *, binding: Optional[dict] = None) -> AtlasState:
    """Missing, corrupt, legacy or wrong-account state refuses startup, never resets."""
    _check_binding(binding)
    if Path(ATLAS_STATE_FILE + ".tmp").exists():
        raise AtlasStateError("Interrupted Atlas save detected; reconcile pending state before startup")
    try:
        with open(ATLAS_STATE_FILE, encoding="utf-8") as stream:
            document = json.load(stream)
    except FileNotFoundError as exc:
        raise AtlasStateError("Atlas state missing; prepare reviewed account history offline") from exc
    except Exception as exc:
        raise AtlasStateError("Atlas state unreadable; preserve file and reconcile offline") from exc
    if not isinstance(document, dict) or document.get("schema") != 2:
        raise AtlasStateError("Legacy/unbound Atlas state; explicit offline reconciliation required")
    stored = document.get("binding")
    _check_binding(stored, stored=True)
    if any(stored.get(key) != value for key, value in binding.items()):
        raise AtlasStateError("Atlas account/server/program/phase/rules binding mismatch")
    state = _validated_state(document.get("state"))
    if state.phase != phase or stored.get("initial_balance") != state.initial_balance:
        raise AtlasStateError("Atlas original capital or phase binding mismatch")
    provenance = document.get("reconciliation", {})
    if not isinstance(provenance, dict) or not provenance.get("reviewed_history"):
        raise AtlasStateError("Atlas reviewed-history provenance missing")
    state._atlas_binding = stored
    state._atlas_reconciliation = provenance
    state._atlas_persistence_ready = True
    log.info("ATLAS: account-bound risk history resumed; no risk anchors reset")
    return state


def _save_atlas_state(state: AtlasState, *, path: Optional[Path] = None) -> None:
    """Atomic durable save; every failure disarms order authorization."""
    state._atlas_persistence_ready = False
    try:
        binding = getattr(state, "_atlas_binding", None)
        _check_binding(binding, stored=True)
        _validated_state(state.to_json())
        if binding.get("phase") != state.phase or binding.get("initial_balance") != state.initial_balance:
            raise AtlasStateError("Atlas immutable phase/capital binding changed")
        document = {"schema": 2, "binding": binding, "state": state.to_json(),
                    "reconciliation": getattr(state, "_atlas_reconciliation", {})}
        target = Path(ATLAS_STATE_FILE) if path is None else Path(path)
        tmp = target.with_name(target.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(document, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    except Exception as exc:
        # A persistent latch and retained pending file complement the in-memory
        # disarm. Offline artifact preparation must never mutate a live latch.
        if path is None:
            try:
                from src.core import ops
                ops.set_halt("Atlas state persistence failed; reconcile account history",
                             "atlas_state_persistence", notify=False)
            except Exception:
                pass
        raise AtlasStateError("Atlas state could not be durably saved; new orders disabled") from exc
    state._atlas_persistence_ready = True


def require_persistence_ready(state: AtlasState, account) -> None:
    """Pre-order/monitor guard: unknown identity or a previous failed save refuses."""
    if not getattr(state, "_atlas_persistence_ready", False):
        raise AtlasStateError("Atlas risk history has not been durably saved")
    binding = getattr(state, "_atlas_binding", {})
    if (account is None or binding.get("login") != getattr(account, "login", None)
            or binding.get("server") != getattr(account, "server", None)
            or binding.get("phase") != state.phase
            or binding.get("initial_balance") != state.initial_balance):
        state._atlas_persistence_ready = False
        raise AtlasStateError("Atlas runtime account identity no longer matches saved risk history")


def _daily_only(reasons) -> bool:
    """True when the only hard Atlas breach is the daily-loss limit (that one resets at the next UTC day)."""
    hard = [r for r in reasons or [] if "_hard:" in str(r) or str(r).startswith("fail_closed")]
    return bool(hard) and all(str(r).startswith("daily_loss_hard:") for r in hard)


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


def _explain_atlas(reasons) -> str:
    """'daily_loss_hard:0.9697>=0.8' -> "today's loss at 97% of the Atlas limit"."""
    out = []
    for r in reasons or []:
        m = re.match(r"(\w+?)_(hard|soft):([\d.]+)>=([\d.]+)", str(r))
        if not m:
            out.append(str(r))
            continue
        what, val, lim = _ATLAS_WORDS.get(m.group(1), m.group(1)), float(m.group(3)), float(m.group(4))
        out.append(f"{what} ${val:,.2f} (limit ${lim:,.2f})" if m.group(1) == "protector"
                   else f"{what} at {val:.0%} of the Atlas limit")
    return "; ".join(out)
