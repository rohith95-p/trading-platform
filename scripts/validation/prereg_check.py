"""Was every result pre-registered before it was run?

The rule in research/DECISIONS.md is that a study declares what it will test and
what would count as a pass BEFORE it runs, so a disappointing result cannot be
re-cut into a good one. That rule is only worth anything if something checks it.

For every RESULT_<name>_<date>.md in research/registry this looks for a matching
PREREG_<name>_*.md (or PROTOCOL_<name>_*.md, the earlier name for the same thing)
and compares the two files' first commit dates in git. A result whose
pre-registration was written later -- or never -- fails. One committed in the
same commit as its result is reported as weak: nothing proves it came first, so
from now on the pre-registration gets its own commit before the run.

Exit code 1 if anything fails, so CI can run it.

    python -I scripts/validation/prereg_check.py
"""
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
REG = os.path.join("research", "registry")


def first_commit(path):
    """When this file first entered git, or None if it is not committed yet."""
    out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", path],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return out[-1] if out else None


def study_name(fname):
    m = re.match(r"(?:PREREG|PROTOCOL|RESULT)_(.+?)_\d{4}-\d{2}-\d{2}\.md$",
                 os.path.basename(fname))
    return m.group(1) if m else None


def main():
    pres, results = {}, {}
    for pattern in ("PREREG_*.md", "PROTOCOL_*.md"):
        for f in sorted(glob.glob(os.path.join(REG, pattern))):
            pres.setdefault(study_name(f), []).append(f)
    for f in sorted(glob.glob(os.path.join(REG, "RESULT_*.md"))):
        results.setdefault(study_name(f), []).append(f)

    if not results:
        print("no results recorded yet")
        return 0

    bad, weak = [], []
    print(f"{'study':28s} {'pre-registered':22s} {'result':22s} order")
    for name, files in sorted(results.items()):
        rf = files[-1]
        pf = pres.get(name, [None])[-1]
        if pf is None:
            bad.append(f"{name}: result {os.path.basename(rf)} has no "
                       f"PREREG_{name}_*.md or PROTOCOL_{name}_*.md")
            print(f"{name:28s} {'MISSING':22s} {os.path.basename(rf)[:22]:22s} FAIL")
            continue
        pc, rc = first_commit(pf), first_commit(rf)
        if pc is None or rc is None:
            state = "not committed yet"
        elif pc == rc:
            state = "same commit (weak)"
            weak.append(f"{name}: pre-registration and result landed in one commit, "
                        f"so nothing proves which came first")
        elif pc < rc:
            state = "ok"
        else:
            state = "FAIL (result first)"
            bad.append(f"{name}: {os.path.basename(rf)} was committed before "
                       f"{os.path.basename(pf)}")
        print(f"{name:28s} {(pc or '-')[:19]:22s} {(rc or '-')[:19]:22s} {state}")

    orphans = sorted(set(pres) - set(results))
    if orphans:
        print("\npre-registered, not yet reported: " + ", ".join(orphans))
    if bad:
        print("\nproblems:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print("\nevery result was pre-registered first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
