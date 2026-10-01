"""Registry of supported ETL patterns and the best practices each one encodes."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.bundle_request import Pattern


@dataclass(frozen=True)
class PatternInfo:
    pattern: Pattern
    template: str
    summary: str
    required_parameters: tuple[str, ...]
    practices: tuple[str, ...]


PATTERNS: dict[Pattern, PatternInfo] = {
    Pattern.INCREMENTAL_LOAD: PatternInfo(
        pattern=Pattern.INCREMENTAL_LOAD,
        template="incremental_load.sql.j2",
        summary="Watermark-based incremental MERGE (upsert) from cloud files into a Delta table",
        required_parameters=("source_path", "destination_schema", "destination_table",
                             "primary_key_columns", "incremental_key"),
        practices=(
            "Idempotent: re-running reprocesses the watermark boundary and MERGE dedupes it",
            "Batch deduplicated by primary key, keeping the latest incremental_key",
            "Only newer source rows overwrite matched target rows",
            "Fails fast on NULL primary keys / required columns via raise_error",
            "Lineage columns (_source_file, _ingested_at) on every row",
            "Run audit row written to _load_audit",
        ),
    ),
    Pattern.FULL_REFRESH: PatternInfo(
        pattern=Pattern.FULL_REFRESH,
        template="full_refresh.sql.j2",
        summary="Atomic CREATE OR REPLACE of a Delta table from a complete source snapshot",
        required_parameters=("source_path", "destination_schema", "destination_table"),
        practices=(
            "Atomic replace keeps Delta history, so a bad load can be rolled back with RESTORE",
            "Fails before replacing if the snapshot is below min_expected_rows",
            "Fails on rows the reader could not parse (_rescued_data) instead of dropping them",
            "Optional primary-key uniqueness and NOT NULL checks before the swap",
            "Lineage columns and _load_audit row",
        ),
    ),
}
