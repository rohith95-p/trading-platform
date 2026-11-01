"""Record-and-check layer on top of SystemConfig.

Every time a backtest run produces a result someone is willing to trust,
record() it here with its exact SystemConfig fingerprint. main_loop.py checks
its live fingerprint against this ledger on startup (see check_live_config())
and refuses to trade on a configuration nobody has actually validated --
instead of silently running whatever the code currently happens to do, which
is how portfolio_v4 ended up live with an unvalidated exposure-cap change and
the D1 gate in a different state than any backtest tested.

This does not judge whether a result is "good" -- a losing backtest can be
recorded too (see HYP-047's pre-fix entry). It only answers "has THIS EXACT
configuration been run through a backtest and had its result written down,"
so a human always knows whether live matches something measured.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.system_config import SystemConfig

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The ledger is configuration, not a research output: main_loop refuses to trade
# a configuration it cannot find in here, so the file has to travel with the
# code. It used to live in research/, which scripts/vps_update.ps1 excludes from
# the copy -- so the VPS never received it, the gate failed there, and the bot
# could only start with ULTRA_ALLOW_UNVALIDATED=1 (2026-11-01). It lives in
# config/ now, which is copied.
LEDGER_PATH = os.path.join(_ROOT, "config", "validation_ledger.json")
LEGACY_LEDGER_PATH = os.path.join(_ROOT, "research", "validation_ledger.json")


def _load() -> List[Dict[str, Any]]:
    path = LEDGER_PATH if os.path.exists(LEDGER_PATH) else LEGACY_LEDGER_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(entries: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)


def record(config: SystemConfig, result: Dict[str, Any], source: str, notes: str = "") -> str:
    """Append a validation entry. Returns the fingerprint recorded under."""
    fp = config.fingerprint()
    entries = _load()
    entries.append({
        "fingerprint": fp,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "result": result,
        "notes": notes,
        "config": config.to_dict(),
    })
    _save(entries)
    return fp


def lookup(fingerprint: str) -> Optional[Dict[str, Any]]:
    """Most recent entry recorded under this exact fingerprint, if any."""
    matches = [e for e in _load() if e["fingerprint"] == fingerprint]
    return matches[-1] if matches else None


def all_entries() -> List[Dict[str, Any]]:
    return _load()


def closest_entry(config: SystemConfig) -> Optional[Dict[str, Any]]:
    """The most recently recorded entry, purely as a diff target when there's
    no exact match -- not a claim it's the 'right' one to compare against."""
    entries = _load()
    return entries[-1] if entries else None


def check_live_config() -> Dict[str, Any]:
    """What main_loop.py calls at startup. Returns a report dict:
    {"validated": bool, "fingerprint": str, "match": entry|None, "diff": [str]}
    """
    live_cfg = SystemConfig.from_live()
    fp = live_cfg.fingerprint()
    match = lookup(fp)
    if match:
        return {"validated": True, "fingerprint": fp, "match": match, "diff": []}

    closest = closest_entry(live_cfg)
    diff: List[str] = []
    if closest:
        closest_cfg = SystemConfig.from_dict(closest["config"])
        diff = live_cfg.diff(closest_cfg)
    return {"validated": False, "fingerprint": fp, "match": closest, "diff": diff}
