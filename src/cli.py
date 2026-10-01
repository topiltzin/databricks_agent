"""Databricks Agent CLI: list, validate, generate, show and commit ETL bundles."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
import yaml

from src.generators.bundle_generator import BUNDLE_FILES, BundleExistsError, write_bundle
from src.generators.patterns import PATTERNS
from src.utils.git_utils import GitError, commit_bundle
from src.validators.bundle_reviewer import review_bundle
from src.validators.request_validator import ValidationResult, validate_request

DEFAULT_BUNDLES_DIR = Path("bundles")


def _load_request(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise click.ClickException(f"{path}: request must be a JSON object")
    return data


def _report(result: ValidationResult, strict: bool, require_request: bool = True) -> bool:
    for issue in result.issues:
        color = "red" if issue.severity.value == "error" else "yellow"
        click.secho(str(issue), fg=color, err=True)
    ok = result.ok if require_request else not result.errors
    passed = ok and not (strict and result.warnings)
    summary = f"{len(result.errors)} error(s), {len(result.warnings)} warning(s)"
    click.secho(("PASS" if passed else "FAIL") + f" — {summary}", fg="green" if passed else "red",
                err=True)
    return passed


@click.group()
def cli() -> None:
    """Generate Databricks ETL bundles that follow data-engineering best practices."""


@cli.command("list-templates")
def list_templates() -> None:
    """List ETL patterns and the best practices each one bakes in."""
    for info in PATTERNS.values():
        click.secho(info.pattern.value, bold=True)
        click.echo(f"  {info.summary}")
        click.echo(f"  required: {', '.join(info.required_parameters)}")
        for practice in info.practices:
            click.echo(f"  - {practice}")


@cli.command()
@click.option("--request", "request_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="Bundle request JSON.")
@click.option("--strict", is_flag=True, help="Treat best-practice warnings as errors.")
def validate(request_path: Path, strict: bool) -> None:
    """Validate a bundle request without generating anything."""
    if not _report(validate_request(_load_request(request_path)), strict):
        sys.exit(1)


@cli.command("generate-bundle")
@click.option("--request", "request_path", type=click.Path(exists=True, path_type=Path),
              required=True, help="Bundle request JSON.")
@click.option("--output-dir", type=click.Path(path_type=Path), default=DEFAULT_BUNDLES_DIR,
              show_default=True)
@click.option("--force", is_flag=True, help="Overwrite an existing bundle directory.")
@click.option("--strict", is_flag=True, help="Refuse to generate if there are warnings.")
def generate_bundle(request_path: Path, output_dir: Path, force: bool, strict: bool) -> None:
    """Validate a request and render it into bundles/<bundle_name>/."""
    result = validate_request(_load_request(request_path))
    if not _report(result, strict):
        sys.exit(1)
    assert result.request is not None
    try:
        target = write_bundle(result.request, output_dir, force=force)
    except BundleExistsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"Generated {target}/", fg="green")
    for name in BUNDLE_FILES:
        click.echo(f"  {name}")


@cli.command()
@click.option("--bundle", "bundle_dir", type=click.Path(exists=True, file_okay=False, path_type=Path),
              required=True)
def show(bundle_dir: Path) -> None:
    """Print every file in a bundle."""
    for name in BUNDLE_FILES:
        path = bundle_dir / name
        if path.exists():
            click.secho(f"===== {name} =====", bold=True)
            click.echo(path.read_text())


@cli.command("list-bundles")
@click.option("--bundles-dir", type=click.Path(path_type=Path), default=DEFAULT_BUNDLES_DIR,
              show_default=True)
def list_bundles(bundles_dir: Path) -> None:
    """List bundles with their version and pattern."""
    for meta_path in sorted(bundles_dir.glob("*/bundle.yml")):
        meta = yaml.safe_load(meta_path.read_text()) or {}
        desc = str(meta.get("description", "")).strip().splitlines()
        click.echo(f"{meta.get('name', meta_path.parent.name):<32} "
                   f"v{meta.get('version', '?'):<8} {meta.get('pattern', '-'):<18} "
                   f"{desc[0] if desc else ''}")


@cli.command()
@click.option("--bundle", "bundle_dirs", multiple=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Bundle directory to review (repeatable). Default: every bundle.")
@click.option("--bundles-dir", type=click.Path(path_type=Path), default=DEFAULT_BUNDLES_DIR,
              show_default=True)
@click.option("--strict", is_flag=True, help="Treat best-practice warnings as errors.")
def review(bundle_dirs: tuple[Path, ...], bundles_dir: Path, strict: bool) -> None:
    """Audit existing bundles: metadata, SQL anti-patterns, job config, and drift from request.json."""
    dirs = list(bundle_dirs) or sorted(p.parent for p in bundles_dir.glob("*/bundle.yml"))
    if not dirs:
        raise click.ClickException(f"no bundles found in {bundles_dir}")
    failed = False
    for bundle_dir in dirs:
        click.secho(f"== {bundle_dir}", bold=True, err=True)
        issues = review_bundle(bundle_dir)
        failed |= not _report(ValidationResult(None, issues), strict, require_request=False)
    if failed:
        sys.exit(1)


@cli.command("commit-bundle")
@click.option("--bundle", "bundle_dir", type=click.Path(exists=True, file_okay=False, path_type=Path),
              required=True)
@click.option("--message", default=None,
              help="Commit message (default: 'feat: Add <name> ETL template — <description>').")
def commit_bundle_cmd(bundle_dir: Path, message: str | None) -> None:
    """Commit one bundle directory as a single atomic Git commit."""
    try:
        sha = commit_bundle(bundle_dir, message)
    except GitError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho(f"Committed {bundle_dir} as {sha[:10]}", fg="green")


if __name__ == "__main__":
    cli()
