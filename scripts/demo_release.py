"""Prepare immutable release/rollback snapshots; never stop processes or trade.

This intentionally replaces the old in-place latest-master updater. A prepared
release is not activated: production switching requires a separately reviewed
maintenance procedure and demo reconciliation. No shell commands are executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import zipfile

CODE_DIRS = {"src", "scripts", "config", "docs", "tests", ".agents", ".github"}
CODE_FILES = {"README.md", "requirements.txt", "pyproject.toml", "start_ultra_core.bat"}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".pfx", ".p12", ".pyc"}
MAX_UNCOMPRESSED = 256 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def permitted(relative: PurePosixPath) -> bool:
    return bool(relative.parts) and not relative.is_absolute() and ".." not in relative.parts and "\\" not in str(relative) and ":" not in str(relative) and (
        relative.parts[0] in CODE_DIRS or relative.as_posix() in CODE_FILES
    ) and not any(
        part.startswith(".env") or part in {"__pycache__", "venv", ".venv", ".git"}
        for part in relative.parts
    ) and relative.suffix.lower() not in FORBIDDEN_SUFFIXES


def _destination(root: Path, label: str) -> Path:
    staging = root.resolve() / "release_staging"
    if staging.is_symlink():
        raise ValueError("Release staging must not be a symlink")
    destination = staging / label
    if destination.exists():
        raise ValueError("Release directory already exists; immutable releases are never overwritten")
    return destination


def _finish(destination: Path, manifest: dict) -> dict:
    manifest["files"] = {
        file.relative_to(destination).as_posix(): sha256(file)
        for file in sorted(destination.rglob("*")) if file.is_file()
    }
    if not manifest["files"]:
        raise ValueError("No permitted release files found")
    (destination / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def prepare_archive(root: Path, archive: Path, revision: str, expected_sha256: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Revision must be a full lowercase 40-character commit SHA")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("An independently supplied archive SHA-256 is required")
    if sha256(archive).lower() != expected_sha256.lower():
        raise ValueError("Archive SHA-256 mismatch")
    destination = _destination(root, revision)
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if sum(item.file_size for item in entries) > MAX_UNCOMPRESSED:
            raise ValueError("Archive exceeds the uncompressed size limit")
        selected = []
        seen = set()
        for item in entries:
            normalized = item.filename.replace("\\", "/")
            path = PurePosixPath(normalized)
            if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
                raise ValueError("Unsafe archive member path")
            if not path.parts or path.parts[0] != "trading-platform-" + revision:
                raise ValueError("Archive root does not match the pinned repository revision")
            relative = PurePosixPath(*path.parts[1:])
            if path.is_absolute() or ".." in path.parts or "\\" in item.filename or ":" in item.filename:
                raise ValueError("Unsafe archive member")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Archive symlinks are not supported")
            if item.is_dir() or not permitted(relative):
                continue
            key = relative.as_posix().casefold()
            if key in seen:
                raise ValueError("Duplicate/case-colliding archive member")
            seen.add(key)
            selected.append((item, relative))
        if not selected:
            raise ValueError("No permitted release files found")
        destination.mkdir(parents=True)
        for item, relative in selected:
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(item) as source, target.open("xb") as output:
                while block := source.read(1024 * 1024):
                    output.write(block)
    _finish(destination, {
        "schema": 1, "kind": "pinned_archive", "revision": revision,
        "archive_sha256": expected_sha256.lower(), "activation": "NOT_ACTIVATED",
        "runtime_state_included": False,
    })
    return destination


def snapshot_current(root: Path, label: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", label):
        raise ValueError("Snapshot label must be a simple directory name")
    root = root.resolve()
    destination = _destination(root, "rollback_" + label)
    sources = []
    for name in sorted(CODE_DIRS | CODE_FILES):
        source = root / name
        if source.is_symlink():
            raise ValueError("Snapshot symlinks are not supported")
        if source.is_file():
            sources.append(source)
        elif source.is_dir():
            sources.extend(source.rglob("*"))
    selected = []
    for source in sources:
        if source.is_symlink():
            raise ValueError("Snapshot symlinks are not supported")
        relative = PurePosixPath(source.relative_to(root).as_posix())
        if source.is_file() and permitted(relative):
            selected.append((source, relative))
    if not selected:
        raise ValueError("No permitted snapshot files found")
    destination.mkdir(parents=True)
    for source, relative in selected:
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    _finish(destination, {
        "schema": 1, "kind": "local_code_rollback", "label": label,
        "activation": "NOT_ACTIVATED", "runtime_state_included": False,
        "warning": "Code/config snapshot only; preserve and reconcile account runtime state separately",
    })
    return destination


def verify_release(directory: Path) -> dict:
    directory = directory.resolve()
    manifest_path = directory / "RELEASE_MANIFEST.json"
    if manifest_path.is_symlink():
        raise ValueError("Release manifest symlinks are not supported")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if manifest.get("schema") != 1 or not isinstance(files, dict) or not files:
        raise ValueError("Invalid release manifest")
    actual = set()
    for file in directory.rglob("*"):
        if file.is_symlink():
            raise ValueError("Release symlinks are not supported")
        if file.is_file() and file != manifest_path:
            actual.add(file.relative_to(directory).as_posix())
    if actual != set(files):
        raise ValueError("Release file set changed")
    for name, expected in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not permitted(path):
            raise ValueError("Unsafe manifest member")
        if sha256(directory.joinpath(*path.parts)) != expected:
            raise ValueError("Release file checksum mismatch")
    return manifest


def owned_processes(root: Path, records: list[dict]) -> list[dict]:
    """Narrow read-only process plan: exact project interpreter AND known entry point."""
    interpreter = os.path.normcase(os.path.abspath(root / "venv" / "Scripts" / "python.exe"))
    modules = {"src.core.main_loop": "trading_loop", "scripts.watchdog": "watchdog",
               "scripts.protect_profit": "protector"}
    scripts = {"scripts/watchdog.py": "watchdog", "scripts/protect_profit.py": "protector"}
    result = []
    for record in records:
        try:
            argv = [part.strip('"') for part in shlex.split(record.get("CommandLine") or "", posix=False)]
            pid = int(record["ProcessId"])
        except (ValueError, KeyError, TypeError):
            continue
        if pid <= 0 or len(argv) < 2:
            continue
        if os.path.normcase(os.path.abspath(argv[0])) != interpreter:
            continue
        role = None
        if len(argv) >= 3 and argv[1] == "-m":
            role = modules.get(argv[2])
        else:
            candidate = Path(argv[1])
            if not candidate.is_absolute():
                candidate = root / candidate
            for name, expected_role in scripts.items():
                if os.path.normcase(os.path.abspath(candidate)) == os.path.normcase(os.path.abspath(root / name)):
                    role = expected_role
        if role:
            result.append({"pid": pid, "role": role})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--archive", type=Path)
    command.add_argument("--snapshot-current", metavar="LABEL")
    command.add_argument("--verify-release", type=Path)
    command.add_argument("--process-snapshot", type=Path)
    parser.add_argument("--revision")
    parser.add_argument("--archive-sha256")
    args = parser.parse_args()
    try:
        if args.archive:
            if not args.revision or not args.archive_sha256:
                parser.error("--archive requires --revision and --archive-sha256")
            path = prepare_archive(args.root, args.archive, args.revision, args.archive_sha256)
            print(json.dumps({"status": "PREPARED_NOT_ACTIVATED", "path": str(path)}))
        elif args.snapshot_current:
            path = snapshot_current(args.root, args.snapshot_current)
            print(json.dumps({"status": "ROLLBACK_SNAPSHOT_PREPARED", "path": str(path)}))
        elif args.verify_release:
            manifest = verify_release(args.verify_release)
            print(json.dumps({"status": "FILES_VERIFIED_NOT_ACTIVATED", "files": len(manifest["files"])}))
        else:
            records = json.loads(args.process_snapshot.read_text(encoding="utf-8-sig"))
            print(json.dumps({"status": "PLAN_ONLY", "owned": owned_processes(args.root, records)}))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

