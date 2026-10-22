---
name: data-architecture
description: Use when designing data platforms, choosing between data lakes/lakehouses/warehouses, or implementing data mesh patterns. Covers modern data architecture approaches.
allowed-tools: Read, Glob, Grep
---

# Data Architecture

Modern data architecture patterns including data lakes, lakehouses, data mesh, and data platform design.

## When to Use This Skill

- Choosing between data lake, warehouse, and lakehouse
- Designing a modern data platform
- Implementing data mesh principles
- Planning data storage strategy
- Understanding data architecture trade-offs

## Data Architecture Evolution

```text
Generation 1: Data Warehouse (1990s-2000s)
- Structured data only
- ETL into warehouse
- Star/snowflake schemas
- SQL-based analytics

Generation 2: Data Lake (2010s)
- All data types (structured, semi, unstructured)
- Schema-on-read
- Hadoop/HDFS based
- Cheap storage, complex processing

Generation 3: Lakehouse (2020s)
- Best of both: lake flexibility + warehouse features
- ACID transactions on lake
- Schema enforcement optional
- Unified analytics and ML
```

## Architecture Comparison

### Data Warehouse

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sources   │ ──► │     ETL     │ ──► │  Warehouse  │
│ (Structured)│     │ (Transform) │     │ (Star/Snow) │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │     BI      │
                                        │  Analytics  │
                                        └─────────────┘

Characteristics:
- Schema-on-write
- Optimized for SQL queries
- Structured data only
- High data quality
- Expensive storage

Best for:
- Business intelligence
- Financial reporting
- Structured analytics
```

### Data Lake

```text
┌─────────────┐     ┌─────────────┐
│   Sources   │ ──► │  Data Lake  │
│    (All)    │     │   (Raw)     │
└─────────────┘     └─────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐     ┌─────────┐     ┌─────────┐
    │   ML    │     │   ETL   │     │  Spark  │
    │ Training│     │ to DW   │     │ Analysis│
    └─────────┘     └─────────┘     └─────────┘

Characteristics:
- Schema-on-read
- All data types
- Cheap storage
- Flexible processing
- Risk of "data swamp"

Best for:
- Data science/ML
- Unstructured data
- Experimental analysis
```

### Data Lakehouse

```text
┌─────────────┐     ┌─────────────────────────────────┐
│   Sources   │ ──► │         Data Lakehouse          │
│    (All)    │     │  ┌──────────────────────────┐   │
└─────────────┘     │  │    Metadata Layer        │   │
                    │  │ (Delta/Iceberg/Hudi)     │   │
                    │  └──────────────────────────┘   │
                    │  ┌──────────────────────────┐   │
                    │  │    Storage Layer         │   │
                    │  │    (Object Storage)      │   │
                    │  └──────────────────────────┘   │
                    └─────────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         ┌─────────┐         ┌─────────┐         ┌─────────┐
         │   SQL   │         │   ML    │         │  Stream │
         │   BI    │         │ Workload│         │ Process │
         └─────────┘         └─────────┘         └─────────┘

Characteristics:
- ACID transactions
- Schema evolution
- Time travel
- Unified batch/streaming
- Open formats

Best for:
- Unified analytics
- Both BI and ML
- Modern data platforms
```

## Architecture Selection Guide

| Factor | Warehouse | Lake | Lakehouse |
| ------ | --------- | ---- | --------- |
| Data types | Structured | All | All |
| Query performance | Excellent | Poor-Medium | Good |
| Data quality | High | Variable | Configurable |
| Cost | High | Low | Medium |
| ML workloads | Limited | Excellent | Excellent |
| Real-time | Limited | Good | Good |
| Governance | Strong | Weak | Strong |
| Complexity | Low | High | Medium |

```text
Decision Tree:

Is data mostly structured with BI focus?
├── Yes → Data Warehouse
└── No
    └── Need ML + BI on same data?
        ├── Yes → Lakehouse
        └── No
            └── Primarily ML/unstructured?
                ├── Yes → Data Lake
                └── No → Lakehouse
```

## Lakehouse Technologies

### Delta Lake (Databricks)

```text
Features:
- ACID transactions
- Time travel (data versioning)
- Schema enforcement/evolution
- Unified batch/streaming
- Optimized performance (Z-ordering, compaction)

File format: Parquet + Delta log
```

### Apache Iceberg (Netflix)

```text
Features:
- ACID transactions
- Hidden partitioning
- Schema evolution
- Time travel
- Vendor neutral

File format: Parquet/ORC/Avro + metadata
```

### Apache Hudi (Uber)

```text
Features:
- ACID transactions
- Incremental processing
- Record-level updates
- Time travel
- Optimized for streaming

File format: Parquet + Hudi metadata
```

### Technology Comparison

| Feature | Delta Lake | Iceberg | Hudi |
| ------- | ---------- | ------- | ---- |
| ACID | Yes | Yes | Yes |
| Time Travel | Yes | Yes | Yes |
| Schema Evolution | Good | Excellent | Good |
| Streaming | Excellent | Good | Excellent |
| Ecosystem | Databricks | Wide | Wide |
| Performance | Excellent | Excellent | Good |
| Community | Large | Growing | Medium |

## Data Mesh

### Principles

```text
Data Mesh = Decentralized data architecture

Four Principles:

1. Domain Ownership
   - Data owned by domain teams
   - Not centralized data team

2. Data as a Product
   - Treat data like a product
   - Quality, discoverability, usability

3. Self-Serve Platform
   - Platform enables domain teams
   - Reduces friction

4. Federated Governance
   - Global standards
   - Local implementation
```

### Data Products

```text
Data Product = Autonomous unit of data

Components:
┌──────────────────────────────────────┐
│           Data Product               │
│  ┌──────────┐  ┌──────────────────┐ │
│  │   Data   │  │     Metadata     │ │
│  │ (Tables) │  │ (Schema, docs)   │ │
│  └──────────┘  └──────────────────┘ │
│  ┌──────────┐  ┌──────────────────┐ │
│  │   Code   │  │      APIs        │ │
│  │ (ETL)    │  │  (Access layer)  │ │
│  └──────────┘  └──────────────────┘ │
│  ┌──────────────────────────────────┐│
│  │         Quality + SLAs           ││
│  └──────────────────────────────────┘│
└──────────────────────────────────────┘
```

### Data Mesh vs Centralized

| Aspect | Centralized | Data Mesh |
| ------ | ----------- | --------- |
| Ownership | Central data team | Domain teams |
| Scaling | Team bottleneck | Scales with org |
| Domain knowledge | Lost in translation | Preserved |
| Governance | Centralized | Federated |
| Implementation | Uniform | Heterogeneous |
| Complexity | Lower initially | Higher initially |

## Data Modeling Patterns

### Star Schema

```text
        ┌─────────────┐
        │  Dim_Time   │
        └──────┬──────┘
               │
┌───────────┐  │  ┌───────────┐
│Dim_Product├──┼──┤Dim_Customer│
└───────────┘  │  └───────────┘
               │
        ┌──────┴──────┐
        │ Fact_Sales  │
        └─────────────┘

Pros: Simple, fast queries
Cons: Denormalized, redundancy
Best for: BI, reporting
```

### Snowflake Schema

```text
Normalized dimensions:
Dim_Product → Dim_Category → Dim_Subcategory

Pros: Less redundancy
Cons: More joins, slower
Best for: Complex hierarchies
```

### Data Vault

```text
Hub (business keys) ←→ Link (relationships) ←→ Satellite (attributes)

Pros: Auditable, flexible, scalable
Cons: Complex, learning curve
Best for: Enterprise data warehouse
```

## Storage Layers

### Bronze/Silver/Gold (Medallion Architecture)

```text
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Bronze  │ ──► │ Silver  │ ──► │  Gold   │
│  (Raw)  │     │(Cleaned)│     │(Curated)│
└─────────┘     └─────────┘     └─────────┘

Bronze: Raw ingestion, append-only
Silver: Cleaned, validated, conformed
Gold: Business-level aggregates, features
```

### Zones in Data Lake

```text
Landing Zone: Raw files from sources
Raw Zone: Structured raw data
Curated Zone: Transformed, quality-checked
Consumption Zone: Ready for analytics
Sandbox Zone: Exploration and experimentation
```

## Best Practices

### Data Quality

```text
Implement quality gates:
- Schema validation
- Null checks
- Range validation
- Referential integrity
- Freshness monitoring
```

### Governance

```text
Key capabilities:
- Data catalog
- Lineage tracking
- Access control
- Privacy compliance
- Audit logging
```

### Performance

```text
Optimization techniques:
- Partitioning (by date, region)
- Clustering/Z-ordering
- Compaction
- Caching
- Materialized views
```

## Related Skills

- `etl-elt-patterns` - Data transformation
- `stream-processing` - Real-time data
- `database-scaling` - Database patterns
