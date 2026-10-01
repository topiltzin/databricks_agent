"""Build the Databricks job-cluster spec (Clusters API `new_cluster` shape)."""

from __future__ import annotations

from typing import Any

from src.models.bundle_request import BundleRequest


def build_cluster_spec(r: BundleRequest) -> dict[str, Any]:
    c = r.cluster_config
    spec: dict[str, Any] = {
        "spark_version": c.spark_version,
        "node_type_id": c.node_type_id,
        "driver_node_type_id": c.driver_node_type_id or c.node_type_id,
    }
    if c.autoscale:
        spec["autoscale"] = {"min_workers": c.autoscale.min_workers,
                             "max_workers": c.autoscale.max_workers}
    else:
        spec["num_workers"] = c.num_workers if c.num_workers is not None else 2
    # SINGLE_USER is the UC-enabled access mode for job clusters.
    spec["data_security_mode"] = "SINGLE_USER"
    if c.photon:
        spec["runtime_engine"] = "PHOTON"
    spec["custom_tags"] = {
        "bundle": r.bundle_name,
        "pattern": r.pattern.value,
        "owner": r.created_by,
    }
    return spec
