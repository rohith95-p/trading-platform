"""Where the studies get the live portfolio's trades from.

Four stop/target studies read "the real entries of the live legs". That file used
to be a hand-placed `trades_no_donchian.json`, with nothing saying which run made
it. It is now whatever the newest audit run wrote, and the run is reproducible:

    python -I scripts/validation/independent_audit_run.py

`trades()` returns {window: {"trades": [...], "halts": [...], "m1": {...}}}.
"""
import glob
import json
import os
from typing import Any, Dict, Tuple

RESULTS = os.path.join("research", "results")
LEGACY = os.path.join(RESULTS, "audit_2026-10-30", "trades_no_donchian.json")


def newest_audit_dir() -> str:
    dirs = sorted(glob.glob(os.path.join(RESULTS, "audit_20*")))
    if not dirs:
        raise FileNotFoundError(
            "no audit run found. Run: python -I scripts/validation/independent_audit_run.py")
    return dirs[-1]


def path() -> str:
    """The trades file to use, newest audit run first."""
    cand = os.path.join(newest_audit_dir(), "trades.json")
    if os.path.exists(cand):
        return cand
    if os.path.exists(LEGACY):
        return LEGACY
    raise FileNotFoundError(
        f"{cand} missing. Run: python -I scripts/validation/independent_audit_run.py")


def trades() -> Tuple[Dict[str, Any], str]:
    p = path()
    with open(p, encoding="utf-8") as fh:
        return json.load(fh), p
