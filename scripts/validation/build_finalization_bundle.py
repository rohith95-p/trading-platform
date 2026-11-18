"""Build a local review/demo-preparation source bundle; never deploy or start it.

Credentials, terminal state, logs, historical data and binaries are excluded.
Includes current working-tree source, with exact hashes and dirty-path disclosure.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/results/finalization_2026-11-18"


def main():
    paths = set()
    for dirname, suffixes in (("src", {".py"}), ("scripts", {".py", ".ps1", ".bat"}),
                              ("tests", {".py"}), ("docs", {".md"}), ("config", {".json"})):
        for p in (ROOT / dirname).rglob("*"):
            if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts:
                paths.add(p)
    for name in ("README.md", "pyproject.toml", "requirements.txt"):
        paths.add(ROOT / name)
    for p in (ROOT / "research").glob("*.md"):
        paths.add(p)
    for p in (ROOT / "research/registry").glob("PREREG_*_2026-11-18.md"):
        paths.add(p)
    for name in ("market_atlas.json", "data_inventory.json", "literature.json", "economic_hurdle.json", "verification.json"):
        path = OUT / name
        if path.exists():
            paths.add(path)
    files = {p.relative_to(ROOT).as_posix():p.read_bytes() for p in sorted(paths)}
    files["BUNDLE_STATUS.md"] = ("# Review bundle, demo preparation only\n\n"
        "No strategy is qualified. This archive does not enable no-order behavior, launch a bot, configure a terminal, or deploy a service.\n"
        "Production strategy source is included for review and remains unchanged by the finalization study.\n"
        "Use docs/DEPLOYMENT_READINESS.md and docs/FINALIZATION_STATUS.md before any demo rehearsal.\n"
        "Credentials, terminal data, historical bars and native dependencies are absent.\n"
        "Input locations and hashes are in research/results/finalization_2026-11-18/data_inventory.json.\n"
        "Reproduce offline checks with an appropriate Python environment: python -m pytest -m \"not live\".\n").encode()
    hashes = {name:hashlib.sha256(data).hexdigest() for name, data in files.items()}
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True).splitlines()
    manifest = {"classification":"source_review_and_demo_preparation_not_deployed", "source_revision":revision,
                "source_is_working_tree":True, "tracked_dirty_paths":dirty,
                "candidate_status":"none_qualified", "production_activated":False,
                "datasets_included":False, "credentials_included":False,
                "files_sha256":hashes}
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "finalization_demo_review.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
        z.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name, digest in hashes.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest
    bundle_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / "bundle_manifest.json").write_text(json.dumps({"bundle":target.name, "sha256":bundle_sha,
        "file_count":len(files), "source_revision":revision, "classification":manifest["classification"]}, indent=2), encoding="utf-8")
    print(json.dumps({"bundle":str(target), "files":len(files), "sha256":bundle_sha}))


if __name__ == "__main__":
    main()
