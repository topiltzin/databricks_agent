# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Databricks Agent** — A CLI tool that helps teams build reusable ETL bundle templates and generate new ETL bundles from specifications. The agent captures best practices for data ingestion, transformation, and orchestration, storing everything in Git for version control and reproducibility.

## Architecture

### Core Components

1. **Template Engine** — Generates ETL bundle configurations from Jinja2 templates
   - Located in `src/templates/`
   - Supports parameterized configurations (table names, schedules, cluster sizes, etc.)
   - Each template encodes a data engineering best practice

2. **Bundle Generator** — Creates new ETL bundles from user specifications
   - Located in `src/generators/`
   - Takes a bundle request (name, source, destination, transformation logic)
   - Generates complete bundle with Spark SQL, Databricks Jobs config, cluster settings

3. **Request Validator** — Validates user input before bundle generation
   - Located in `src/validators/`
   - Ensures required fields (source connector, destination, transformation logic)
   - Catches invalid configurations early

4. **Best Practices Library** — Curated ETL patterns
   - Located in `bundles/` directory
   - Patterns for batch ingestion, incremental loads, CDC pipelines, data quality checks
   - Each bundle is a Git-tracked, production-ready template

### Data Flow

```
User Request (JSON)
    ↓
Validator (schema check)
    ↓
Generator (render Jinja2 templates)
    ↓
Bundle Output (YAML config + SQL + job definitions)
    ↓
Git Commit (version control)
```

### Git-Based Version Control Strategy

- **Bundles directory**: All bundle templates and generated configs are in Git
- **Commit per bundle**: Each new bundle creation is one atomic commit
- **Bundle metadata**: `bundle.yml` in each bundle root with version, description, lineage
- **Auditability**: Git history serves as audit trail; see who created/modified bundles and when

## Development Workflow

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize git repo (if not already done)
git init
git config user.email "your-email@example.com"
git config user.name "Your Name"
```

### Common Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # once

# List ETL patterns and the best practices each encodes
python -m src.cli list-templates

# Validate a request (no generation). --strict also fails on best-practice warnings
python -m src.cli validate --request examples/etl_request_incremental.json

# Generate bundles/<bundle_name>/ from a request (--force to regenerate, --output-dir to redirect)
python -m src.cli generate-bundle --request examples/etl_request_incremental.json

# Audit bundles: metadata, SQL anti-patterns, job config, drift from request.json
python -m src.cli review [--bundle bundles/orders_incremental_load] [--strict]

python -m src.cli show --bundle bundles/orders_incremental_load
python -m src.cli list-bundles

# Commit only that bundle dir; default message follows the convention below
python -m src.cli commit-bundle --bundle bundles/orders_incremental_load

# Tests / lint
pytest
pytest tests/test_generators.py::test_incremental_load_s3_to_uc -v
ruff check src tests
```

### Testing Strategy

- `tests/test_validators.py`: schema + best-practice rules, cron → Quartz conversion
- `tests/test_generators.py`: rendered SQL/YAML content, determinism, request.json round-trip
- `tests/test_reviewer.py`: **snapshot test** — every bundle in `bundles/` must equal what its
  `request.json` generates. After changing a template, regenerate bundles with `--force`
  and review the diff before committing.
- `tests/test_cli.py`: CLI commands, including `commit-bundle` against a temp git repo
- Fixtures come from `examples/*.json` (`tests/conftest.py`)

## Tech Stack

- **Language**: Python 3.11+
- **Templating**: Jinja2 with `StrictUndefined` for SQL; YAML configs are built as dicts and dumped
  with PyYAML (no YAML-quoting bugs from templating)
- **Validation**: Pydantic (`extra="forbid"`, so typos in requests fail)
- **Testing**: pytest
- **Linting**: ruff, black, mypy
- **CLI**: Click
- **Version Control**: Git (all bundles stored as code)

## Directory Structure

```
databricks-agent/
├── src/
│   ├── cli.py                        # list-templates, validate, generate-bundle, review, show, list-bundles, commit-bundle
│   ├── models/bundle_request.py      # Pydantic request schema (Pattern, parameters, cluster, job)
│   ├── validators/
│   │   ├── request_validator.py      # Errors (block) vs warnings (best-practice deviations)
│   │   └── bundle_reviewer.py        # Lints existing bundles + detects drift from request.json
│   ├── generators/
│   │   ├── bundle_generator.py       # Pure render_bundle(request) -> {file: content}; write_bundle
│   │   ├── patterns.py               # Pattern registry: template, required params, practices
│   │   ├── spark_job_builder.py      # Jobs API 2.1 job + Asset Bundle (databricks.yml)
│   │   ├── cluster_config_builder.py # Job cluster spec
│   │   └── cron.py                   # 5-field cron validation and Quartz conversion
│   ├── templates/                    # Jinja2 SQL: _macros.sql.j2, incremental_load.sql.j2, full_refresh.sql.j2
│   └── utils/git_utils.py            # Atomic per-bundle commits
├── bundles/                          # Generated bundles (never hand-edited) + README.md
│   └── <bundle_name>/                # request.json, bundle.yml, pipeline.sql, cluster_config.yml,
│                                     # job_config.yml, databricks.yml
├── examples/                         # Bundle requests (also test fixtures)
└── tests/
```

## Important Conventions

- **Bundle Naming**: snake_case, descriptive (e.g., `orders_incremental_load`)
- **request.json is the source of truth**: never hand-edit generated files; change the request
  (or a template) and regenerate. `review` and the test suite fail on drift.
- **Bundle Metadata** (`bundle.yml`): version, description, created_by, created_at, supported runtimes, lineage, data-quality guarantees
- **Commit Messages**: Format: `feat: Add <bundle_name> ETL template — <one-line description>`
- **Git Tracking**: All bundles are versioned; regenerating a bundle creates a new commit
- **Idempotency**: Generating the same request twice produces byte-identical output (`created_at` is pinned in request.json)
- **SQL safety**: every identifier interpolated into SQL is validated as a plain identifier

## Databricks-Specific Notes

- Generated SQL needs Databricks Runtime 14.1+ (SQL session variables); default is 15.4 LTS and
  non-LTS runtimes produce a warning
- Unity Catalog three-level names are required; liquid clustering (`cluster_by`) preferred over partitions
- Job clusters use `SINGLE_USER` access mode, Photon, and cost tags; schedules are converted to Quartz
- Data quality checks use `raise_error` so failures stop the job before bad data is published
  (NULL/duplicate keys, row-count floor, `_rescued_data`, optional freshness SLA)
- Test bundles in Databricks Community Edition or mock environments
- Store cluster/job configs in YAML for GitOps workflow
