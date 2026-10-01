"""Build the Databricks Jobs API 2.1 job definition for a bundle."""

from __future__ import annotations

from typing import Any

from src.generators.cluster_config_builder import build_cluster_spec
from src.generators.cron import to_quartz
from src.models.bundle_request import BundleRequest

JOB_CLUSTER_KEY = "etl_cluster"


def build_job_spec(r: BundleRequest) -> dict[str, Any]:
    j = r.job_config
    job: dict[str, Any] = {
        "name": r.bundle_name,
        "description": r.description.strip(),
        "tags": {"bundle": r.bundle_name, "pattern": r.pattern.value, "owner": r.created_by},
        # Ephemeral job cluster: cheaper than all-purpose and isolated per run.
        "job_clusters": [{"job_cluster_key": JOB_CLUSTER_KEY, "new_cluster": build_cluster_spec(r)}],
        "tasks": [
            {
                "task_key": r.pattern.value,
                "job_cluster_key": JOB_CLUSTER_KEY,
                "notebook_task": {
                    "notebook_path": f"{j.workspace_root.rstrip('/')}/{r.bundle_name}/pipeline",
                    "source": "WORKSPACE",
                },
                "timeout_seconds": j.timeout_seconds,
                "max_retries": j.max_retries,
                "min_retry_interval_millis": 300_000,
                "retry_on_timeout": False,
            }
        ],
        "schedule": {
            "quartz_cron_expression": to_quartz(j.schedule),
            "timezone_id": j.timezone,
            "pause_status": "UNPAUSED",
        },
        "max_concurrent_runs": j.max_concurrent_runs,
        "timeout_seconds": j.timeout_seconds,
        "queue": {"enabled": True},
    }
    if j.email_on_failure:
        job["email_notifications"] = {"on_failure": list(j.email_on_failure)}
    return job


def build_asset_bundle(r: BundleRequest) -> dict[str, Any]:
    """Databricks Asset Bundle config, deployable with `databricks bundle deploy`.

    dev uses development mode (resources prefixed per user, schedules paused); prod deploys
    to a shared workspace path.
    """
    job = build_job_spec(r)
    for task in job["tasks"]:
        task["notebook_task"] = {"notebook_path": "./pipeline.sql"}
    return {
        "bundle": {"name": r.bundle_name},
        "resources": {"jobs": {r.bundle_name: job}},
        "targets": {
            "dev": {"mode": "development", "default": True},
            "prod": {
                "mode": "production",
                "workspace": {"root_path": f"{r.job_config.workspace_root.rstrip('/')}/{r.bundle_name}"},
            },
        },
    }
