"""Real-Git provenance tests: timestamps alone cannot establish pre-registration."""
from pathlib import Path
import os
import subprocess

import pytest

from scripts.validation import prereg_check


@pytest.fixture
def repo(tmp_path):
    def git(*args, env=None):
        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True,
            capture_output=True, text=True, env=proc_env,
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.email", "provenance-test@example.invalid")
    git("config", "user.name", "Provenance Test")
    (tmp_path / "research" / "registry").mkdir(parents=True)
    git("commit", "--allow-empty", "-m", "root")
    return tmp_path, git


def write(root, prefix, *, date="2026-11-18", text="fixed protocol"):
    file = root / "research" / "registry" / f"{prefix}_Example_{date}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    return file.relative_to(root).as_posix()


def commit(git, path, *, date=None):
    git("add", "--", path)
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else None
    git("commit", "-m", path, env=env)
    return git("rev-parse", "HEAD")


def test_prior_ancestor_passes_even_with_reversed_commit_dates(repo, capsys):
    root, git = repo
    pre = write(root, "PREREG")
    pc = commit(git, pre, date="2026-11-19T12:00:00+00:00")
    result = write(root, "RESULT")
    rc = commit(git, result, date="2026-11-18T12:00:00+00:00")
    assert prereg_check.first_commit(pre, root) == pc
    assert prereg_check.is_ancestor(pc, rc, root)
    assert prereg_check.main(root) == 0
    assert "1 verified, 0 weak, 0 failed" in capsys.readouterr().out


def test_result_before_prereg_fails_despite_misleading_dates(repo):
    root, git = repo
    commit(git, write(root, "RESULT"), date="2026-11-20T12:00:00+00:00")
    commit(git, write(root, "PREREG"), date="2026-11-17T12:00:00+00:00")
    assert prereg_check.main(root) == 1


def test_divergent_branch_additions_are_not_prior_ancestry(repo):
    root, git = repo
    git("checkout", "-b", "protocol")
    commit(git, write(root, "PREREG"))
    git("checkout", "main")
    commit(git, write(root, "RESULT"))
    git("merge", "--no-ff", "protocol", "-m", "merge protocol after result")
    assert prereg_check.main(root) == 1


@pytest.mark.parametrize("committed", [None, "PREREG", "RESULT"])
def test_uncommitted_pair_members_fail(repo, committed):
    root, git = repo
    if committed:
        commit(git, write(root, committed))
    write(root, "PREREG")
    write(root, "RESULT")
    assert prereg_check.main(root) == 1


def test_missing_protocol_fails(repo):
    root, git = repo
    commit(git, write(root, "RESULT"))
    assert prereg_check.main(root) == 1


def test_same_commit_is_explicit_weak_and_strict_mode_fails(repo, capsys):
    root, git = repo
    pre, result = write(root, "PREREG"), write(root, "RESULT")
    git("add", "--", pre, result)
    git("commit", "-m", "both together")
    assert prereg_check.main(root) == 0
    output = capsys.readouterr().out
    assert "0 verified, 1 weak, 0 failed" in output
    assert "All recorded results have" not in output
    assert prereg_check.main(root, strict_weak=True) == 1


@pytest.mark.parametrize("staged", [False, True])
def test_dirty_evidence_cannot_borrow_old_commits(repo, staged):
    root, git = repo
    pre = write(root, "PREREG")
    commit(git, pre)
    commit(git, write(root, "RESULT"))
    (root / pre).write_text("changed after observing result", encoding="utf-8")
    if staged:
        git("add", "--", pre)
    assert prereg_check.main(root) == 1


def test_each_result_checked_not_only_latest(repo, capsys):
    root, git = repo
    commit(git, write(root, "RESULT", date="2026-11-17"))
    commit(git, write(root, "PREREG"))
    commit(git, write(root, "RESULT"))
    assert prereg_check.main(root) == 1
    assert "1 verified, 0 weak, 1 failed" in capsys.readouterr().out


def test_legacy_protocol_and_orphan_are_supported(repo):
    root, git = repo
    commit(git, write(root, "PROTOCOL"))
    commit(git, write(root, "RESULT"))
    (root / "research" / "registry" / "PREREG_Pending_2026-11-18.md").write_text("pending")
    assert prereg_check.main(root) == 0
