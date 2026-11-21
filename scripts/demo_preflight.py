"""Read-only dedicated-demo preflight; presence-only unless explicitly connected.

This is a diagnostic, never a bot launcher. It imports no production modules,
loads no .env secrets, calls no order API and modifies no account settings.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path


class ReadOnlyTerminal:
    """Only expose terminal reads required by this diagnostic; all order paths fail."""
    def __init__(self, terminal):
        self._terminal = terminal

    def __getattr__(self, name):
        if name not in {"initialize", "shutdown", "account_info", "terminal_info", "symbol_info",
                        "symbol_info_tick", "positions_get", "orders_get", "copy_rates_from_pos",
                        "copy_ticks_range"}:
            raise PermissionError("Operation unavailable in read-only demo preflight")
        return getattr(self._terminal, name)


def presence(root: Path) -> dict:
    return {
        "status": "PRESENCE_ONLY_NOT_CONNECTED",
        "project_python_present": (root / "venv" / "Scripts" / "python.exe").is_file(),
        "local_settings_present": (root / ".env.local").is_file(),
        "native_mt5_module_available": importlib.util.find_spec("MetaTrader5") is not None,
        "account_demo_verified": False,
        "release_order_enabled": False,
        "note": "File/package presence is not proof of demo login, VPS access or operational readiness",
    }


def assess(terminal, expected_login: int, expected_server: str, symbol: str) -> dict:
    """Inspect existing terminal identity without logging account identifiers or cash."""
    if expected_login <= 0 or not expected_server or symbol not in {"XAUUSD", "XAUUSDm"}:
        raise ValueError("Explicit demo identity and supported XAUUSD symbol required")
    read = ReadOnlyTerminal(terminal)
    if not read.initialize():
        return {"status": "REFUSED", "reasons": ["terminal_initialization_failed"], "release_order_enabled": False}
    try:
        account, connection = read.account_info(), read.terminal_info()
        reasons = []
        if account is None:
            reasons.append("account_unknown")
        else:
            if getattr(account, "trade_mode", None) != 0:  # MT5 ACCOUNT_TRADE_MODE_DEMO
                reasons.append("account_is_not_verified_demo")
            if getattr(account, "login", None) != expected_login or getattr(account, "server", None) != expected_server:
                reasons.append("account_identity_mismatch")
            if getattr(account, "margin_mode", None) != 2:
                reasons.append("hedging_mode_required")
        if connection is None or not getattr(connection, "connected", False):
            reasons.append("terminal_disconnected")
        info = read.symbol_info(symbol)
        for attribute in ("point", "trade_contract_size", "volume_min", "volume_step"):
            value = getattr(info, attribute, None)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                reasons.append("symbol_specification_invalid_" + attribute)
        positions, orders = read.positions_get(), read.orders_get()
        if positions is None or orders is None:
            reasons.append("exposure_query_failed")
        elif len(positions) or len(orders):
            reasons.append("dedicated_empty_demo_required")
        return {
            "status": "READ_ONLY_DEMO_IDENTITY_VERIFIED" if not reasons else "REFUSED",
            "reasons": reasons, "release_order_enabled": False,
            "account_demo_verified": account is not None and getattr(account, "trade_mode", None) == 0,
            "note": "Identity/read checks only; no executable strategy, real-tick parity or deployment approval is implied",
        }
    finally:
        read.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--connect-readonly", action="store_true")
    parser.add_argument("--expected-demo-login", type=int)
    parser.add_argument("--expected-demo-server")
    parser.add_argument("--symbol", default="XAUUSDm")
    args = parser.parse_args()
    if not args.connect_readonly:
        print(json.dumps(presence(args.root)))
        return 0
    if not args.expected_demo_login or not args.expected_demo_server:
        parser.error("Read-only connection requires explicit --expected-demo-login and --expected-demo-server")
    import MetaTrader5 as terminal
    try:
        result = assess(terminal, args.expected_demo_login, args.expected_demo_server, args.symbol)
    except Exception:
        # Terminal errors can include identifiers; intentionally omit raw messages.
        result = {"status": "REFUSED", "reasons": ["read_only_inspection_failed"], "release_order_enabled": False}
    print(json.dumps(result))
    return 0 if result["status"] == "READ_ONLY_DEMO_IDENTITY_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
