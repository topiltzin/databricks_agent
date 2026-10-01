"""Commit a bundle directory as one atomic Git commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml


class GitError(RuntimeError):
    pass


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def default_commit_message(bundle_dir: Path) -> str:
    meta = yaml.safe_load((bundle_dir / "bundle.yml").read_text())
    summary = str(meta["description"]).strip().splitlines()[0]
    return f"feat: Add {meta['name']} ETL template — {summary}"


def commit_bundle(bundle_dir: Path, message: str | None = None) -> str:
    """Stage and commit only `bundle_dir`. Returns the new commit SHA."""
    bundle_dir = bundle_dir.resolve()
    if not (bundle_dir / "bundle.yml").exists():
        raise GitError(f"{bundle_dir} is not a bundle (no bundle.yml)")
    root = Path(_git(bundle_dir, "rev-parse", "--show-toplevel"))
    rel = str(bundle_dir.relative_to(root))
    _git(root, "add", "--", rel)
    if not _git(root, "diff", "--cached", "--name-only", "--", rel):
        raise GitError(f"nothing to commit in {rel}")
    msg = message or default_commit_message(bundle_dir)
    _git(root, "commit", "-m", msg, "--", rel)
    return _git(root, "rev-parse", "HEAD")
