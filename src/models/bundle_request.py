"""Pydantic schema for an ETL bundle request (the agent's input contract)."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_SPARK_VERSION = "15.4.x-scala2.12"


class Pattern(str, Enum):
    INCREMENTAL_LOAD = "incremental_load"
    FULL_REFRESH = "full_refresh"


class _Strict(BaseModel):
    # Typos in a request should fail loudly, not be silently ignored.
    model_config = ConfigDict(extra="forbid")


class BundleParameters(_Strict):
    source_path: str
    source_format: Literal["parquet", "csv", "json", "avro", "orc"] = "parquet"
    destination_catalog: str | None = None
    destination_schema: str
    destination_table: str

    # Keys
    primary_key_columns: list[str] = Field(default_factory=list)
    incremental_key: str | None = None

    # Layout: liquid clustering is preferred over Hive-style partitioning on UC.
    cluster_by: list[str] = Field(default_factory=list)
    partition_columns: list[str] = Field(default_factory=list)

    # CSV options
    has_header: bool = True
    delimiter: str = ","

    # Data quality
    not_null_columns: list[str] = Field(default_factory=list)
    min_expected_rows: int = Field(default=1, ge=0)
    freshness_sla_hours: int | None = Field(default=None, gt=0)


class Autoscale(_Strict):
    min_workers: int = Field(ge=1)
    max_workers: int = Field(ge=1)


class ClusterConfig(_Strict):
    spark_version: str = DEFAULT_SPARK_VERSION
    node_type_id: str = "i3.xlarge"
    driver_node_type_id: str | None = None
    num_workers: int | None = Field(default=None, ge=0)
    autoscale: Autoscale | None = None
    photon: bool = True


class JobConfig(_Strict):
    schedule: str = "0 2 * * *"  # standard 5-field cron, converted to Quartz on generation
    timezone: str = "UTC"
    max_concurrent_runs: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=3600, ge=0)
    max_retries: int = Field(default=1, ge=0)
    email_on_failure: list[str] = Field(default_factory=list)
    workspace_root: str = "/Workspace/ETL"


class BundleRequest(_Strict):
    bundle_name: str
    pattern: Pattern
    description: str
    version: str = "1.0.0"
    created_by: str = "data-team"
    created_at: date | None = None
    parameters: BundleParameters
    cluster_config: ClusterConfig = Field(default_factory=ClusterConfig)
    job_config: JobConfig = Field(default_factory=JobConfig)

    @property
    def target_table(self) -> str:
        p = self.parameters
        parts = [p.destination_catalog, p.destination_schema, p.destination_table]
        return ".".join(x for x in parts if x)

    @property
    def audit_table(self) -> str:
        p = self.parameters
        parts = [p.destination_catalog, p.destination_schema, "_load_audit"]
        return ".".join(x for x in parts if x)
