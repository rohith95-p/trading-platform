"""Check committed pre-registration order using Git ancestry, not commit dates.

Every RESULT document must have a matching PREREG (or legacy PROTOCOL), and
both must be committed with clean working-tree contents. First introduction
of the protocol must be a strict ancestor of first introduction of the result.
This verifies recorded provenance, not when an experiment actually executed or
whether its rules were followed. A shallow/incomplete history is insufficient.

Legacy same-commit records remain WEAK for compatibility, never a verified
pass. Use --strict-weak to reject them in a release/evidence gate.

    python -I scripts/validation/prereg_check.py [--strict-weak]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def first_commit(path: str, root: Path = ROOT) -> str | None:
    """Return the earliest addition commit hash, or None for an uncommitted file."""
    commits = _git(root, "log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    return commits[-1] if commits else None


def is_ancestor(before: str, after: str, root: Path = ROOT) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", before, after],
        cwd=root, capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Git ancestry could not be established: " + result.stderr.strip())
    return result.returncode == 0


def study_name(fname: str) -> str | None:
    match = re.match(
        r"(?:PREREG|PROTOCOL|RESULT)_(.+?)_\d{4}-\d{2}-\d{2}\.md$",
        os.path.basename(fname),
    )
    return match.group(1) if match else None


def main(root: Path = ROOT, *, strict_weak: bool = False) -> int:
    root = Path(root)
    registry = root / "research" / "registry"
    pres: dict[str, list[str]] = {}
    results: dict[str, list[str]] = {}
    for pattern in ("PREREG_*.md", "PROTOCOL_*.md"):
        for file in sorted(registry.glob(pattern)):
            name = study_name(file.name)
            if name is not None:
                pres.setdefault(name, []).append(file.relative_to(root).as_posix())
    for file in sorted(registry.glob("RESULT_*.md")):
        name = study_name(file.name)
        if name is not None:
            results.setdefault(name, []).append(file.relative_to(root).as_posix())

    if not results:
        print("No result documents recorded; no completed study provenance to verify.")
        return 0

    bad, weak = [], []
    verified = 0
    print(f"{'study/result':48s} {'prereg commit':14s} {'result commit':14s} order")
    for name, files in sorted(results.items()):
        # Preserve the registry's latest-protocol convention, but inspect every
        # result rather than allowing a newer record to hide an earlier failure.
        pf = pres.get(name, [None])[-1]
        for rf in files:
            label = os.path.basename(rf)
            if pf is None:
                bad.append(f"{label}: no matching PREREG_{name}_*.md or PROTOCOL_{name}_*.md")
                print(f"{label:48s} {'MISSING':14s} {'-':14s} FAIL")
                continue
            pc = rc = None
            try:
                pc, rc = first_commit(pf, root), first_commit(rf, root)
                if pc is None or rc is None:
                    state = "FAIL (not committed)"
                    bad.append(f"{label}: pre-registration and result must both be committed")
                elif _git(root, "status", "--porcelain", "--", pf, rf):
                    state = "FAIL (uncommitted changes)"
                    bad.append(f"{label}: protocol/result working-tree contents differ from committed evidence")
                elif pc == rc:
                    state = "WEAK (same commit; order unproven)"
                    weak.append(f"{label}: protocol and result first appear in the same commit")
                elif is_ancestor(pc, rc, root):
                    state = "VERIFIED (prereg ancestor)"
                    verified += 1
                else:
                    state = "FAIL (prereg is not a prior ancestor)"
                    bad.append(f"{label}: protocol introduction is later than or unrelated to result introduction")
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                state = "FAIL (Git provenance unavailable)"
                bad.append(f"{label}: {exc}")
            print(f"{label:48s} {(pc or '-')[:12]:14s} {(rc or '-')[:12]:14s} {state}")

    orphans = sorted(set(pres) - set(results))
    if orphans:
        print("\nPre-registered, not yet reported: " + ", ".join(orphans))
    if weak:
        print("\nWEAK historical records; not verified pre-registration:")
        for item in weak:
            print("  - " + item)
    if bad:
        print("\nFAILURES:")
        for item in bad:
            print("  - " + item)
    print(f"\nProvenance summary: {verified} verified, {len(weak)} weak, {len(bad)} failed.")
    if bad or (strict_weak and weak):
        return 1
    if weak:
        print("Compatibility check passed with weak records; use --strict-weak to reject them.")
    else:
        print("All recorded results have committed prior-ancestor pre-registrations.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-weak", action="store_true")
    arguments = parser.parse_args()
    raise SystemExit(main(strict_weak=arguments.strict_weak))
