import json
import subprocess

from click.testing import CliRunner

from src.cli import cli

EXAMPLE = "examples/etl_request_incremental.json"


def run(*args):
    return CliRunner().invoke(cli, list(args))


def test_list_templates():
    result = run("list-templates")
    assert result.exit_code == 0
    assert "incremental_load" in result.output and "full_refresh" in result.output


def test_validate_pass_and_fail(tmp_path, incremental_request):
    assert run("validate", "--request", EXAMPLE).exit_code == 0
    incremental_request["parameters"]["primary_key_columns"] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(incremental_request))
    result = run("validate", "--request", str(bad))
    assert result.exit_code == 1
    assert "primary_key_columns" in result.output


def test_strict_fails_on_warnings(tmp_path, incremental_request):
    incremental_request["job_config"]["email_on_failure"] = []
    req = tmp_path / "req.json"
    req.write_text(json.dumps(incremental_request))
    assert run("validate", "--request", str(req)).exit_code == 0
    assert run("validate", "--request", str(req), "--strict").exit_code == 1


def test_generate_show_list(tmp_path):
    out = tmp_path / "bundles"
    result = run("generate-bundle", "--request", EXAMPLE, "--output-dir", str(out))
    assert result.exit_code == 0, result.output
    assert run("generate-bundle", "--request", EXAMPLE, "--output-dir", str(out)).exit_code == 1
    show = run("show", "--bundle", str(out / "orders_incremental_load"))
    assert "MERGE INTO production.raw_events.orders" in show.output
    listing = run("list-bundles", "--bundles-dir", str(out))
    assert "orders_incremental_load" in listing.output and "incremental_load" in listing.output


def test_commit_bundle(tmp_path):
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True,
                                     text=True).stdout
    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "unrelated.txt").write_text("should not be committed")
    out = tmp_path / "bundles"
    assert run("generate-bundle", "--request", EXAMPLE, "--output-dir", str(out)).exit_code == 0

    result = run("commit-bundle", "--bundle", str(out / "orders_incremental_load"))
    assert result.exit_code == 0, result.output
    assert git("log", "-1", "--format=%s").startswith(
        "feat: Add orders_incremental_load ETL template — Daily incremental load")
    assert "unrelated.txt" in git("status", "--porcelain")
    assert run("commit-bundle", "--bundle", str(out / "orders_incremental_load")).exit_code == 1


def test_review(tmp_path):
    out = tmp_path / "bundles"
    run("generate-bundle", "--request", EXAMPLE, "--output-dir", str(out))
    assert run("review", "--bundles-dir", str(out), "--strict").exit_code == 0
    (out / "orders_incremental_load" / "job_config.yml").write_text("name: x\n")
    result = run("review", "--bundles-dir", str(out))
    assert result.exit_code == 1 and "drift" in result.output
