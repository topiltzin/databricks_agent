import pytest

from src.generators.cron import cron_error, to_quartz
from src.validators.request_validator import validate_request


def fields(result, severity):
    return {i.field for i in result.issues if i.severity.value == severity}


def test_examples_are_clean(incremental_request, full_refresh_request):
    for req in (incremental_request, full_refresh_request):
        result = validate_request(req)
        assert result.ok and not result.warnings, result.issues


def test_unknown_field_is_rejected(incremental_request):
    incremental_request["parameters"]["primary_keys"] = ["order_id"]  # typo
    result = validate_request(incremental_request)
    assert not result.ok
    assert "parameters.primary_keys" in fields(result, "error")


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda r: r.update(bundle_name="OrdersLoad"), "bundle_name"),
        (lambda r: r["parameters"].update(primary_key_columns=[]), "parameters.primary_key_columns"),
        (lambda r: r["parameters"].pop("incremental_key"), "parameters.incremental_key"),
        (lambda r: r["parameters"].pop("destination_catalog"), "parameters.destination_catalog"),
        (lambda r: r["parameters"].update(source_path="my-bucket/data"), "parameters.source_path"),
        (lambda r: r["parameters"].update(primary_key_columns=["id; DROP TABLE x"]),
         "parameters.primary_key_columns"),
        (lambda r: r["parameters"].update(partition_columns=["dt"]), "parameters.partition_columns"),
        (lambda r: r["cluster_config"].update(spark_version="13.3.x-scala2.12"),
         "cluster_config.spark_version"),
        (lambda r: r["cluster_config"].update(num_workers=4), "cluster_config"),
        (lambda r: r["job_config"].update(schedule="0 2 * *"), "job_config.schedule"),
        (lambda r: r["job_config"].update(email_on_failure=["not-an-email"]),
         "job_config.email_on_failure"),
    ],
)
def test_best_practice_errors(incremental_request, mutate, field):
    mutate(incremental_request)
    result = validate_request(incremental_request)
    assert not result.ok
    assert field in fields(result, "error")


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda r: r["parameters"].update(cluster_by=[], partition_columns=["order_date"]),
         "parameters.partition_columns"),
        (lambda r: r["job_config"].update(email_on_failure=[]), "job_config.email_on_failure"),
        (lambda r: r["job_config"].update(max_concurrent_runs=3), "job_config.max_concurrent_runs"),
        (lambda r: r["cluster_config"].update(spark_version="15.1.x-scala2.12"),
         "cluster_config.spark_version"),
    ],
)
def test_best_practice_warnings(incremental_request, mutate, field):
    mutate(incremental_request)
    result = validate_request(incremental_request)
    assert result.ok
    assert field in fields(result, "warning")


def test_full_refresh_does_not_need_keys(full_refresh_request):
    full_refresh_request["parameters"]["primary_key_columns"] = []
    assert validate_request(full_refresh_request).ok


@pytest.mark.parametrize(
    "cron, quartz",
    [
        ("0 2 * * *", "0 0 2 * * ?"),
        ("0 1 * * 0", "0 0 1 ? * 1"),
        ("30 6 * * 1-5", "0 30 6 ? * 2-6"),
        ("*/15 * * * *", "0 */15 * * * ?"),
        ("0 3 1 * *", "0 0 3 1 * ?"),
    ],
)
def test_cron_to_quartz(cron, quartz):
    assert to_quartz(cron) == quartz


@pytest.mark.parametrize("cron", ["0 2 * *", "60 * * * *", "0 2 1 * 1", "0 2 * * MON", "0 5-2 * * *"])
def test_invalid_cron(cron):
    assert cron_error(cron) is not None
