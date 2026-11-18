"""Prepare reviewed Atlas account-state migration offline; never install live state.

The operator supplies complete authoritative anchors and an explicit review note.
The tool cannot verify dashboard/history truth. It refuses reductions relative
 to a readable source and never silently creates or resets runtime risk state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from src.core import atlas_bridge
from src.atlas import load_rules


def prepare_reconciliation(*, source: Path | None, reviewed: Path, output: Path,
                           binding: dict, note: str, recover_unreadable: bool = False,
                           new_account: bool = False) -> Path:
    if not note or len(note.strip()) < 20:
        raise ValueError("Describe authoritative history/anchor review explicitly (at least20 characters)")
    if (source is None) != new_account:
        raise ValueError("Use a source for an existing account, or explicitly declare --new-account")
    output = output.resolve()
    if output == Path(atlas_bridge.ATLAS_STATE_FILE).resolve() or output.exists():
        raise ValueError("Output must be a new offline artifact, never live runtime state")
    if output == reviewed.resolve() or (source is not None and output == source.resolve()):
        raise ValueError("Original and reviewed evidence must never be overwritten")
    raw = json.loads(reviewed.read_text(encoding="utf-8-sig"))
    state = atlas_bridge._validated_state(raw)
    source_hash, source_status = None, "explicit_new_account"
    if source is not None:
        previous = None
        try:
            payload = source.read_bytes()
            source_hash = hashlib.sha256(payload).hexdigest()
            document = json.loads(payload.decode("utf-8-sig"))
            if isinstance(document, dict) and document.get("schema") == 2:
                prior_binding = document.get("binding", {})
                if any(prior_binding.get(key) != value for key, value in binding.items()):
                    raise ValueError("Source belongs to a different account/program/phase/rules")
                document = document.get("state")
            previous = atlas_bridge._validated_state(document)
        except (OSError, json.JSONDecodeError, UnicodeError, atlas_bridge.AtlasStateError):
            if not recover_unreadable:
                raise ValueError("Missing/unreadable source requires explicit --recover-unreadable-source")
            source_status = "explicit_unavailable_source_recovery"
        if previous is not None:
            source_status = "readable_source_preserved"
            if previous.phase != state.phase or previous.initial_balance != state.initial_balance:
                raise ValueError("Migration must preserve original capital and phase")
            if state.peak_equity < previous.peak_equity or state.protector_strikes < previous.protector_strikes:
                raise ValueError("Migration cannot reduce peak equity or erase strikes")
            if previous.day_ref_date_utc == state.day_ref_date_utc:
                if state.day_ref_equity < previous.day_ref_equity or state.day_high_equity < previous.day_high_equity:
                    raise ValueError("Migration cannot loosen same-day risk anchors")
            for day, profit in previous.cycle_day_profits.items():
                if state.cycle_day_profits.get(day) != profit:
                    raise ValueError("Migration cannot erase or rewrite payout-cycle day history")
            if previous.last_trade_ts is not None and (state.last_trade_ts is None or state.last_trade_ts < previous.last_trade_ts):
                raise ValueError("Migration cannot erase last-trade history")
    bound = atlas_bridge.bind_reconciled_state(raw, binding, {
        "reviewed_history": note.strip(), "source_sha256": source_hash,
        "reviewed_state_sha256": hashlib.sha256(reviewed.read_bytes()).hexdigest(),
        "source_status": source_status,
        "operator_truth_not_independently_verified": True,
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas_bridge._save_atlas_state(bound, path=output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--reviewed-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--account-login", type=int, required=True)
    parser.add_argument("--account-server", required=True)
    parser.add_argument("--phase", choices=["evaluation", "funded"], required=True)
    parser.add_argument("--review-note", required=True)
    parser.add_argument("--recover-unreadable-source", action="store_true")
    parser.add_argument("--new-account", action="store_true")
    args = parser.parse_args()
    try:
        rules = load_rules(allow_unverified=atlas_bridge.ALLOW_UNVERIFIED)
        binding = atlas_bridge.account_binding(SimpleNamespace(login=args.account_login, server=args.account_server), args.phase, rules)
        output = prepare_reconciliation(source=args.source, reviewed=args.reviewed_state, output=args.output,
                                        binding=binding, note=args.review_note,
                                        recover_unreadable=args.recover_unreadable_source, new_account=args.new_account)
        print(json.dumps({"status": "PREPARED_OFFLINE_NOT_INSTALLED", "output": str(output)}))
    except Exception:
        print(json.dumps({"status": "REFUSED", "reason": "State preparation failed; preserve source and review identity/anchors offline"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
