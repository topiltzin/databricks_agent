import json

import pytest
import yaml

from src.generators.bundle_generator import (
    BUNDLE_FILES,
    BundleExistsError,
    render_bundle,
    write_bundle,
)
from src.models.bundle_request import BundleRequest


def render(data):
    return render_bundle(BundleRequest.model_validate(data))


def test_all_files_rendered_without_leftover_placeholders(incremental_request, full_refresh_request):
    for req in (incremental_request, full_refresh_request):
        files = render(req)
        assert set(files) == set(BUNDLE_FILES)
        for content in files.values():
            assert "{{" not in content and "{%" not in content


def test_rendering_is_deterministic(incremental_request):
    assert render(incremental_request) == render(incremental_request)


def test_incremental_load_s3_to_uc(incremental_request):
    incremental_request["parameters"]["primary_key_columns"] = ["order_id", "line_id"]
    sql = render(incremental_request)["pipeline.sql"]
    assert sql.startswith("-- Databricks notebook source")
    assert "CREATE TABLE IF NOT EXISTS production.raw_events.orders\nCLUSTER BY (order_date)\nAS" in sql
    assert "ON t.order_id = s.order_id\n  AND t.line_id = s.line_id\nWHEN MATCHED" in sql
    assert "PARTITION BY order_id, line_id ORDER BY updated_at DESC" in sql
    assert "WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *" in sql
    assert "WHERE order_id IS NULL OR line_id IS NULL" in sql
    assert "INTERVAL 26 HOURS" in sql
    assert "INSERT INTO production.raw_events._load_audit" in sql


def test_full_refresh_checks_run_before_replace(full_refresh_request):
    sql = render(full_refresh_request)["pipeline.sql"]
    replace_at = sql.index("CREATE OR REPLACE TABLE production.analytics.dim_customer")
    for check in ("expected >= 1000", "_rescued_data IS NOT NULL", "duplicate primary keys"):
        assert sql.index(check) < replace_at
    assert "header => true" in sql and "delimiter => ','" in sql
    assert "SELECT * EXCEPT (_rescued_data) FROM source_raw" in sql


def test_partitioning_fallback(full_refresh_request):
    full_refresh_request["parameters"]["partition_columns"] = ["country"]
    assert "PARTITIONED BY (country)\nAS" in render(full_refresh_request)["pipeline.sql"]


def test_job_and_cluster_config(incremental_request):
    files = render(incremental_request)
    cluster = yaml.safe_load(files["cluster_config.yml"])
    job = yaml.safe_load(files["job_config.yml"])
    assert cluster["data_security_mode"] == "SINGLE_USER"
    assert cluster["autoscale"] == {"min_workers": 2, "max_workers": 8}
    assert "num_workers" not in cluster
    assert job["job_clusters"][0]["new_cluster"] == cluster
    assert job["schedule"]["quartz_cron_expression"] == "0 0 2 * * ?"
    assert job["max_concurrent_runs"] == 1
    assert job["email_notifications"]["on_failure"] == ["data-team@company.com"]
    assert job["tasks"][0]["notebook_task"]["notebook_path"] == \
        "/Workspace/ETL/orders_incremental_load/pipeline"


def test_asset_bundle(incremental_request):
    dab = yaml.safe_load(render(incremental_request)["databricks.yml"])
    job = dab["resources"]["jobs"]["orders_incremental_load"]
    assert job["tasks"][0]["notebook_task"] == {"notebook_path": "./pipeline.sql"}
    assert dab["targets"]["dev"] == {"mode": "development", "default": True}
    assert dab["targets"]["prod"]["mode"] == "production"


def test_bundle_metadata(incremental_request):
    meta = yaml.safe_load(render(incremental_request)["bundle.yml"])
    for key in ("name", "version", "description", "created_by", "created_at",
                "supported_runtimes", "lineage"):
        assert key in meta
    assert meta["created_at"] == "2026-10-01"
    assert meta["lineage"]["destination"]["table"] == "production.raw_events.orders"


def test_request_json_roundtrips(incremental_request):
    stored = json.loads(render(incremental_request)["request.json"])
    assert render(stored) == render(incremental_request)


def test_write_bundle_refuses_overwrite(tmp_path, incremental_request):
    req = BundleRequest.model_validate(incremental_request)
    target = write_bundle(req, tmp_path)
    assert sorted(p.name for p in target.iterdir()) == sorted(BUNDLE_FILES)
    with pytest.raises(BundleExistsError):
        write_bundle(req, tmp_path)
    write_bundle(req, tmp_path, force=True)
