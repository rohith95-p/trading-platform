"""Operator CLI for the persistent halt latch (src/core/ops.py).

    python -m scripts.halt status
    python -m scripts.halt set --reason "manual stop"
    python -m scripts.halt clear --note "reconciled with broker, positions flat, cause = ..."

A halt survives crashes and restarts; only `clear` (with a written note) removes it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core import ops  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("set")
    s.add_argument("--reason", required=True)
    c = sub.add_parser("clear")
    c.add_argument("--note", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        st = ops.halt_status()
        print("NOT HALTED" if st is None else f"HALTED: {st}")
        return 0 if st is None else 2
    if a.cmd == "set":
        ops.set_halt(a.reason, "operator")
        print("halt latched")
        return 0
    try:
        done = ops.clear_halt(a.note)
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print("halt cleared (archived)" if done else "no halt was set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
