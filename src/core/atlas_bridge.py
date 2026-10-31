"""Everything between this bot and the Atlas rule engine.

Pulled out of main_loop.py on 2026-11-01. It holds the saved-state file (so a
restart keeps Atlas's real peak and daily reference rather than inventing new
ones), the translation from an MT5 account into the rule engine's AccountInfo,
and the plain-English reading of a breach reason.

`RUNTIME` is the live engine/state/monitor, filled in by main_loop once the
account is known and read by anything that needs the current Atlas floors.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

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


def _init_atlas(balance: float, equity: float) -> tuple:
    """Load Atlas rules, create engine + state + MCP monitor. Returns (engine, state, monitor) or raises."""
    rules = load_rules(allow_unverified=ALLOW_UNVERIFIED)
    engine = AtlasRuleEngine(rules)
    phase = os.environ.get("ULTRA_ATLAS_PHASE", "evaluation")
    now_utc = datetime.now(timezone.utc)
    state = _load_atlas_state(phase)
    if state is None:
        state = AtlasState.new(initial_balance=balance, now_utc=now_utc, phase=phase, equity=equity)
        log.warning(f"ATLAS: no saved state -- starting fresh from balance ${balance:,.2f}")
    _save_atlas_state(state)
    monitor = AtlasMCPMonitor(poll_interval=300.0)
    monitor.start()
    return engine, state, monitor


def _load_atlas_state(phase: str) -> Optional[AtlasState]:
    """Saved peak / daily reference, so a restart keeps Atlas's real floors. None = start fresh."""
    try:
        with open(ATLAS_STATE_FILE, encoding="utf-8") as f:
            st = AtlasState.from_json(json.load(f))
    except FileNotFoundError:
        return None
    except Exception as e:
        log.error(f"ATLAS: saved state unreadable ({e}) -- starting fresh")
        return None
    if st.phase != phase:
        log.warning(f"ATLAS: saved state is for phase {st.phase}, running {phase} -- starting fresh")
        return None
    log.info(f"ATLAS: resumed saved state (start ${st.initial_balance:,.2f}, peak ${st.peak_equity:,.2f}, "
             f"day ref ${st.day_ref_equity:,.2f} {st.day_ref_date_utc})")
    return st


def _save_atlas_state(state: AtlasState) -> None:
    try:
        tmp = ATLAS_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state.to_json(), f)
        os.replace(tmp, ATLAS_STATE_FILE)
    except OSError as e:
        log.warning(f"ATLAS: could not save state: {e}")


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
