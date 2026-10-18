"""scope.py -- two ledgers on one account (2026-10-18).

STRATEGY view  (this bot's own magic numbers): entries, "one position at a time", exits/flatten actions, streak
               breakers, per-strategy P&L attribution, protect_profit.
ACCOUNT view   (every magic, every system): daily loss, floating P&L, equity drawdown, exposure, margin, halt state.

Another system trading the same account must never be attributed to Ultra Core, but it must always count toward the
account's risk. If it holds XAUUSDm exposure, Ultra Core blocks new entries (fail closed) and alerts; it never closes or
modifies the foreign position unless account-wide flatten is explicitly enabled (ULTRA_ACCOUNT_WIDE_FLATTEN=1).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterable, List, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(_ROOT, "config", "ultra_magics.json")


class ScopeConfigError(RuntimeError):
    pass


def load_own_magics(path: str = None) -> frozenset:
    """Allowlist of Ultra Core magic numbers. Fails closed: a missing/invalid file raises."""
    p = path or CONFIG_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        magics = data["ultra_core_magics"]
        if not isinstance(magics, list) or not magics or not all(isinstance(m, int) and not isinstance(m, bool) and m > 0 for m in magics):
            raise ValueError("ultra_core_magics must be a non-empty list of positive integers")
        return frozenset(magics)
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ScopeConfigError(f"cannot load Ultra Core magic allowlist from {p}: {e}")


def split_positions(positions: Iterable[Any], own: frozenset) -> Tuple[List[Any], List[Any]]:
    own_p, foreign = [], []
    for p in positions or []:
        (own_p if getattr(p, "magic", None) in own else foreign).append(p)
    return own_p, foreign


def foreign_report(foreign: Iterable[Any]) -> List[Dict[str, Any]]:
    out = []
    for p in foreign:
        out.append({"risk_scope": "account", "magic": getattr(p, "magic", None), "ticket": getattr(p, "ticket", None),
                    "symbol": getattr(p, "symbol", None),
                    "kind": "pending" if hasattr(p, "volume_current") and not hasattr(p, "profit") else "position",
                    "volume": getattr(p, "volume", getattr(p, "volume_current", None)),
                    "direction": "BUY" if getattr(p, "type", 0) == 0 else "SELL",
                    "floating_pl": round(float(getattr(p, "profit", 0.0)) + float(getattr(p, "swap", 0.0)), 2),
                    "comment": str(getattr(p, "comment", ""))[:40]})
    return out


def check_portfolio_magics(portfolio_classes: Iterable[Any], own: frozenset) -> List[int]:
    """Magics used by PORTFOLIO strategies that are missing from the allowlist (must be empty)."""
    missing = []
    for cls in portfolio_classes:
        m = int(cls().magic)
        if m not in own:
            missing.append(m)
    return missing


def account_wide_flatten_enabled() -> bool:
    return os.environ.get("ULTRA_ACCOUNT_WIDE_FLATTEN", "").strip().lower() in ("1", "true", "yes", "on")


def block_on_foreign_enabled() -> bool:
    return os.environ.get("ULTRA_BLOCK_ON_FOREIGN", "1").strip().lower() not in ("0", "false", "no", "off")
