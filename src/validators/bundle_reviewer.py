"""Review an existing bundle directory against the agent's best practices.

Generated bundles (with request.json) are re-validated and re-rendered to detect hand edits
(drift). Hand-written bundles are linted for common Databricks SQL / Jobs mistakes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from src.generators.bundle_generator import BUNDLE_FILES, render_bundle
from src.validators.request_validator import Issue, Severity, validate_request

ERR, WARN = Severity.ERROR, Severity.WARNING
REQUIRED_METADATA = ("name", "version", "description", "created_by", "created_at",
                     "supported_runtimes", "lineage")

# (pattern, severity, message) applied to pipeline.sql of any bundle.
SQL_RULES: list[tuple[re.Pattern[str], Severity, str]] = [
    (re.compile(r"DECLARE\s+@", re.IGNORECASE), ERR, "T-SQL variable syntax; use DECLARE VARIABLE (DBR 14.1+)"),
    (re.compile(r"COUNT\s*\(\s*DISTINCT\s+\*\s*\)", re.IGNORECASE), ERR, "COUNT(DISTINCT *) is not valid Spark SQL"),
    (re.compile(r"^\s*ASSERT\b", re.IGNORECASE | re.MULTILINE), ERR, "ASSERT is not a SQL statement; use raise_error()"),
    (re.compile(r"'s3://\{\{|'[a-z0-9]+://s3://", re.IGNORECASE), ERR, "URI scheme prefixed to a path that already has one"),
    (re.compile(r"\{\{|\{%"), WARN, "unrendered Jinja placeholder; the file cannot run as-is"),
]


def review_bundle(bundle_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for name in ("bundle.yml", "pipeline.sql", "cluster_config.yml", "job_config.yml"):
        if not (bundle_dir / name).exists():
            issues.append(Issue(ERR, name, "missing required bundle file"))

    meta = _load_yaml(bundle_dir / "bundle.yml", issues)
    if isinstance(meta, dict):
        for key in REQUIRED_METADATA:
            if key not in meta:
                issues.append(Issue(ERR, "bundle.yml", f"missing metadata field {key!r}"))
        if meta.get("name") not in (None, bundle_dir.name):
            issues.append(Issue(ERR, "bundle.yml", f"name {meta['name']!r} != directory name"))

    request_path = bundle_dir / "request.json"
    if request_path.exists():
        issues += _review_generated(bundle_dir, request_path)
    else:
        issues.append(Issue(WARN, "request.json",
                            "missing: bundle is not reproducible by the generator"))

    sql_path = bundle_dir / "pipeline.sql"
    if sql_path.exists():
        issues += _lint_sql(sql_path.read_text())
    job = _load_yaml(bundle_dir / "job_config.yml", issues)
    if isinstance(job, dict):
        issues += _lint_job(job)
    return issues


def _load_yaml(path: Path, issues: list[Issue]) -> Any:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        issues.append(Issue(ERR, path.name, f"invalid YAML: {exc}"))
        return None


def _review_generated(bundle_dir: Path, request_path: Path) -> list[Issue]:
    result = validate_request(json.loads(request_path.read_text()))
    issues = [Issue(i.severity, f"request.json:{i.field}", i.message) for i in result.issues]
    if result.request is None:
        return issues
    if result.request.bundle_name != bundle_dir.name:
        issues.append(Issue(ERR, "request.json:bundle_name", "does not match directory name"))
    expected = render_bundle(result.request)
    for name in BUNDLE_FILES:
        path = bundle_dir / name
        if path.exists() and path.read_text() != expected[name]:
            issues.append(Issue(ERR, name, "drift: differs from generator output; "
                                           "edit request.json and regenerate with --force"))
    return issues


def _lint_sql(sql: str) -> list[Issue]:
    issues = [Issue(sev, "pipeline.sql", msg) for rx, sev, msg in SQL_RULES if rx.search(sql)]
    if "raise_error" not in sql:
        issues.append(Issue(WARN, "pipeline.sql",
                            "no failing data quality checks (raise_error); bad data loads silently"))
    if "_load_audit" not in sql:
        issues.append(Issue(WARN, "pipeline.sql", "no run audit (_load_audit)"))
    return issues


def _lint_job(job: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    cron = str((job.get("schedule") or {}).get("quartz_cron_expression", ""))
    if cron and len(cron.split()) < 6:
        issues.append(Issue(ERR, "job_config.yml",
                            f"quartz_cron_expression {cron!r} is 5-field Unix cron; Quartz needs 6-7"))
    if int(job.get("max_concurrent_runs", 1)) > 1:
        issues.append(Issue(WARN, "job_config.yml", "max_concurrent_runs > 1"))
    if not (job.get("email_notifications") or {}).get("on_failure"):
        issues.append(Issue(WARN, "job_config.yml", "no on_failure notifications"))
    if not job.get("job_clusters"):
        issues.append(Issue(WARN, "job_config.yml",
                            "no job_clusters; use ephemeral job clusters, not all-purpose clusters"))
    return issues
