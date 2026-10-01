"""Validate bundle requests: schema (Pydantic) first, then data-engineering best-practice rules.

Errors block generation. Warnings flag deviations from best practice that may be intentional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import ValidationError

from src.generators.cron import cron_error
from src.models.bundle_request import BundleRequest, Pattern

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SOURCE_URI = re.compile(r"^(s3://|abfss://|gs://|/Volumes/)\S+$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RUNTIME = re.compile(r"^(\d+)\.(\d+)\.x-")

# SQL session variables (DECLARE VARIABLE) used by the templates need DBR 14.1+.
MIN_RUNTIME = (14, 1)
LTS_RUNTIMES = {(14, 3), (15, 4), (16, 4), (17, 3)}


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    severity: Severity
    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value.upper()}] {self.field}: {self.message}"


@dataclass
class ValidationResult:
    request: BundleRequest | None
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return self.request is not None and not self.errors


def validate_request(data: dict[str, Any]) -> ValidationResult:
    try:
        request = BundleRequest.model_validate(data)
    except ValidationError as exc:
        issues = [
            Issue(Severity.ERROR, ".".join(str(p) for p in err["loc"]) or "<root>", err["msg"])
            for err in exc.errors()
        ]
        return ValidationResult(None, issues)
    return ValidationResult(request, list(_best_practice_issues(request)))


def _best_practice_issues(r: BundleRequest):  # type: ignore[no-untyped-def]
    err, warn = Severity.ERROR, Severity.WARNING
    p, c, j = r.parameters, r.cluster_config, r.job_config

    # Naming & metadata
    if not SNAKE_CASE.match(r.bundle_name):
        yield Issue(err, "bundle_name", "must be snake_case (e.g. orders_incremental_load)")
    if not SEMVER.match(r.version):
        yield Issue(err, "version", "must be semantic version MAJOR.MINOR.PATCH")
    if len(r.description.strip()) < 15:
        yield Issue(warn, "description", "describe the business purpose (>= 15 chars)")

    # Identifiers are interpolated into SQL, so they must be plain identifiers.
    identifiers = {
        "parameters.destination_catalog": [p.destination_catalog] if p.destination_catalog else [],
        "parameters.destination_schema": [p.destination_schema],
        "parameters.destination_table": [p.destination_table],
        "parameters.primary_key_columns": p.primary_key_columns,
        "parameters.incremental_key": [p.incremental_key] if p.incremental_key else [],
        "parameters.cluster_by": p.cluster_by,
        "parameters.partition_columns": p.partition_columns,
        "parameters.not_null_columns": p.not_null_columns,
    }
    for field, names in identifiers.items():
        for name in names:
            if not IDENTIFIER.match(name):
                yield Issue(err, field, f"{name!r} is not a valid SQL identifier")

    # Source
    if not SOURCE_URI.match(p.source_path) or "'" in p.source_path:
        yield Issue(err, "parameters.source_path",
                    "must be a cloud URI (s3://, abfss://, gs://) or UC Volume path (/Volumes/...)")
    if p.source_format == "csv" and (len(p.delimiter) != 1 or p.delimiter in "'\\"):
        yield Issue(err, "parameters.delimiter", "must be a single character other than ' or \\")

    # Governance: Unity Catalog three-level namespace
    if not p.destination_catalog:
        yield Issue(err, "parameters.destination_catalog",
                    "required: Unity Catalog tables use catalog.schema.table")

    # Pattern-specific rules
    if r.pattern is Pattern.INCREMENTAL_LOAD:
        if not p.primary_key_columns:
            yield Issue(err, "parameters.primary_key_columns", "required for MERGE-based upserts")
        if not p.incremental_key:
            yield Issue(err, "parameters.incremental_key", "required to compute the watermark")
        elif p.incremental_key in p.primary_key_columns:
            yield Issue(warn, "parameters.incremental_key",
                        "is part of the primary key, so updates will insert new rows")
    if r.pattern is Pattern.FULL_REFRESH and p.min_expected_rows == 0:
        yield Issue(warn, "parameters.min_expected_rows",
                    "0 lets an empty snapshot wipe the table; set a realistic floor")
    if p.freshness_sla_hours and r.pattern is not Pattern.INCREMENTAL_LOAD:
        yield Issue(err, "parameters.freshness_sla_hours",
                    "only supported for incremental_load (needs a timestamp incremental_key)")

    # Table layout
    if p.partition_columns and p.cluster_by:
        yield Issue(err, "parameters.partition_columns", "use cluster_by or partition_columns, not both")
    elif p.partition_columns:
        yield Issue(warn, "parameters.partition_columns",
                    "prefer liquid clustering (cluster_by) for new Unity Catalog tables")
    if len(p.cluster_by) > 4:
        yield Issue(err, "parameters.cluster_by", "liquid clustering supports at most 4 columns")

    # Compute
    m = RUNTIME.match(c.spark_version)
    if not m:
        yield Issue(err, "cluster_config.spark_version", "expected format like 15.4.x-scala2.12")
    else:
        rt = (int(m.group(1)), int(m.group(2)))
        if rt < MIN_RUNTIME:
            yield Issue(err, "cluster_config.spark_version",
                        "generated SQL needs DBR 14.1+ (SQL session variables)")
        elif rt not in LTS_RUNTIMES:
            yield Issue(warn, "cluster_config.spark_version",
                        "use an LTS runtime for production jobs: "
                        + ", ".join(f"{a}.{b}" for a, b in sorted(LTS_RUNTIMES)))
    if c.num_workers is not None and c.autoscale is not None:
        yield Issue(err, "cluster_config", "set num_workers or autoscale, not both")
    if c.autoscale and c.autoscale.min_workers > c.autoscale.max_workers:
        yield Issue(err, "cluster_config.autoscale", "min_workers must be <= max_workers")

    # Orchestration
    cron = cron_error(j.schedule)
    if cron:
        yield Issue(err, "job_config.schedule", cron)
    if j.max_concurrent_runs > 1:
        yield Issue(warn, "job_config.max_concurrent_runs",
                    "> 1 lets overlapping runs race on the same MERGE target")
    if j.timeout_seconds == 0:
        yield Issue(warn, "job_config.timeout_seconds", "0 means no timeout; hung runs burn compute")
    if not j.email_on_failure:
        yield Issue(warn, "job_config.email_on_failure", "no one is alerted when the job fails")
    for addr in j.email_on_failure:
        if not EMAIL.match(addr):
            yield Issue(err, "job_config.email_on_failure", f"{addr!r} is not an email address")
