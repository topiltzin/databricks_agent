from pathlib import Path

import pytest

from src.generators.bundle_generator import write_bundle
from src.models.bundle_request import BundleRequest
from src.validators.bundle_reviewer import review_bundle

BUNDLES_DIR = Path(__file__).resolve().parent.parent / "bundles"


def errors(issues):
    return [i for i in issues if i.severity.value == "error"]


@pytest.mark.parametrize("bundle_dir", sorted(p.parent for p in BUNDLES_DIR.glob("*/bundle.yml")),
                         ids=lambda p: p.name)
def test_committed_bundles_match_generator(bundle_dir):
    """Snapshot test: every bundle in the repo is exactly what its request.json generates."""
    assert review_bundle(bundle_dir) == []


@pytest.fixture
def bundle(tmp_path, incremental_request):
    return write_bundle(BundleRequest.model_validate(incremental_request), tmp_path)


def test_generated_bundle_is_clean(bundle):
    assert review_bundle(bundle) == []


def test_hand_edit_is_reported_as_drift(bundle):
    sql = bundle / "pipeline.sql"
    sql.write_text(sql.read_text().replace("s.updated_at > t.updated_at", "true"))
    assert [i.field for i in errors(review_bundle(bundle))] == ["pipeline.sql"]


def test_hand_written_bundle_is_linted(tmp_path):
    b = tmp_path / "legacy"
    b.mkdir()
    (b / "bundle.yml").write_text("name: legacy\nversion: 1.0.0\n")
    (b / "cluster_config.yml").write_text("num_workers: 2\n")
    (b / "job_config.yml").write_text("schedule:\n  quartz_cron_expression: '0 2 * * *'\n")
    (b / "pipeline.sql").write_text(
        "DECLARE @n INT;\nASSERT @n > 0;\nSELECT COUNT(DISTINCT *) FROM read_files('S3://{{ p }}');\n")
    messages = " | ".join(str(i) for i in review_bundle(b))
    for expected in ("missing metadata field 'description'", "T-SQL", "COUNT(DISTINCT *)",
                     "ASSERT", "scheme", "Quartz needs", "not reproducible", "no run audit",
                     "no failing data quality checks", "no on_failure"):
        assert expected in messages
