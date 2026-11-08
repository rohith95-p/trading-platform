import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_requirements_file_exists_and_pinned():
    """Verify requirements.txt exists and has pinned versions (==) for all dependencies."""
    req_file = REPO_ROOT / "requirements.txt"
    assert req_file.exists(), "requirements.txt must exist at repo root"
    
    content = req_file.read_text(encoding="utf-8")
    required_packages = [
        "MetaTrader5",
        "numpy",
        "pandas",
        "scipy",
        "psutil",
        "pytest",
        "python-dotenv",
        "requests",
        "yfinance",
    ]
    for pkg in required_packages:
        pattern = rf"^{re.escape(pkg)}==[\w\.\-]+.*$"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        assert match, f"{pkg} must be pinned with '==' in requirements.txt"


def test_pyproject_toml_has_dependencies():
    """Verify pyproject.toml defines project metadata and pinned dependencies."""
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.exists(), "pyproject.toml must exist"
    
    content = pyproject_file.read_text(encoding="utf-8")
    assert "dependencies = [" in content, "pyproject.toml must declare dependencies under [project]"
    
    for pkg in ["MetaTrader5", "numpy", "pandas", "scipy", "psutil", "python-dotenv", "requests", "yfinance"]:
        assert pkg.lower() in content.lower(), f"{pkg} must be listed in pyproject.toml dependencies"


def test_declared_dependencies_are_actually_importable():
    """requirements.txt is only a promise until something imports it.

    The other tests in this file check that the FILE pins versions. They passed
    for weeks while `scipy` was not installed at all and `pandas` was 2.1.3
    against a declared 3.0.5 -- so `src/research/metrics.deflated_sharpe_ratio`
    was unrunnable and nobody noticed (2026-11-09). This checks the environment,
    not the text file.
    """
    import importlib

    # module name -> import name, where they differ
    modules = {
        "numpy": "numpy",
        "pandas": "pandas",
        "scipy": "scipy",
        "psutil": "psutil",
        "requests": "requests",
        "python-dotenv": "dotenv",
    }
    broken = []
    for pkg, mod in modules.items():
        try:
            importlib.import_module(mod)
        except Exception as exc:          # ImportError, or numpy ABI ValueError
            broken.append("%s (import %s): %s: %s"
                          % (pkg, mod, type(exc).__name__, str(exc)[:120]))
    assert not broken, (
        "declared dependencies that do not import in this environment:\n  "
        + "\n  ".join(broken)
        + "\nrun: python -m pip install -r requirements.txt")


def test_installed_versions_match_requirements():
    """A pinned version that is not the installed version is a silent trap.

    pandas 2.1.3 installed against pandas==3.0.5 declared is how numpy got
    upgraded under a pandas that needed numpy<2, breaking imports mid-session.
    """
    from importlib.metadata import PackageNotFoundError, version

    req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    mismatched = []
    for line in req.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name = line.split("==", 1)[0].strip()
        want = line.split("==", 1)[1].split(";", 1)[0].strip()
        if ";" in line and "win32" in line and os.name != "nt":
            continue
        try:
            have = version(name)
        except PackageNotFoundError:
            mismatched.append("%s: declared %s, NOT INSTALLED" % (name, want))
            continue
        if have != want:
            mismatched.append("%s: declared %s, installed %s" % (name, want, have))
    assert not mismatched, (
        "installed packages do not match requirements.txt:\n  "
        + "\n  ".join(mismatched)
        + "\nrun: python -m pip install -r requirements.txt")
