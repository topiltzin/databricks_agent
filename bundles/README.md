# Databricks ETL Bundle Library

Every bundle here is **generated** by the Databricks Agent from its `request.json`. Do not edit
bundle files by hand: change the request and regenerate. `python -m src.cli review` (and the
test suite) fails if a bundle drifts from what its request generates.

## Bundles

| Bundle | Pattern | What it does |
|---|---|---|
| `orders_incremental_load` | `incremental_load` | Daily upsert of S3 Parquet order events into `production.raw_events.orders` |
| `customer_dimensions_weekly` | `full_refresh` | Weekly atomic replace of `production.analytics.dim_customer` from a vendor CSV |

## Bundle layout

```
<bundle_name>/
├── request.json        # Source of truth: the validated request this bundle was generated from
├── bundle.yml          # Metadata: version, owner, runtimes, lineage, data-quality guarantees
├── pipeline.sql        # Databricks SQL notebook (runs on DBR 14.1+, LTS 15.4 by default)
├── cluster_config.yml  # Job cluster spec (UC SINGLE_USER access mode, Photon, cost tags)
├── job_config.yml      # Databricks Jobs API 2.1 definition (Quartz schedule, retries, alerts)
└── databricks.yml      # Asset Bundle config: `databricks bundle deploy -t dev|prod`
```

## Best practices every bundle gets

- **Idempotent runs**: incremental loads MERGE on the primary key and only overwrite with newer
  rows; full refreshes replace atomically (roll back with `RESTORE TABLE ... TO VERSION AS OF`).
- **Data quality checks that stop the run**: `raise_error` fails the job on NULL keys, duplicate
  keys, too few rows, rows the reader could not parse (`_rescued_data`) or stale data, *before*
  bad data reaches consumers.
- **Lineage and audit**: every row gets `_source_file` and `_ingested_at` columns; every run
  writes a row to `<catalog>.<schema>._load_audit`.
- **Governance**: Unity Catalog three-level names, liquid clustering instead of partitioning.
- **Operations**: ephemeral job clusters, LTS runtimes, one run at a time, timeouts, retries,
  failure emails.

## Workflow

```bash
python -m src.cli validate --request examples/etl_request_incremental.json
python -m src.cli generate-bundle --request examples/etl_request_incremental.json  # add --force to regenerate
python -m src.cli review --strict
python -m src.cli commit-bundle --bundle bundles/orders_incremental_load
cd bundles/orders_incremental_load && databricks bundle deploy -t dev
```

## Adding a pattern

1. Add a value to `Pattern` in `src/models/bundle_request.py` and an entry in
   `src/generators/patterns.py`.
2. Add `src/templates/<pattern>.sql.j2` (reuse the macros in `_macros.sql.j2`).
3. Add pattern rules to `src/validators/request_validator.py`.
4. Add an example request, generate the bundle, and add tests.
