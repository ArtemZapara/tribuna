# ADR 0001: Use storage by workload

- Status: accepted
- Date: 2026-09-11

## Context

Tribuna handles relational metadata, large immutable media, and dense tracking
observations. A single storage engine would either complicate local development or
perform poorly for one of those workloads.

## Decision

- Store projects, matches, timelines, dataset metadata, events, annotations, and job
  state in SQLite locally and PostgreSQL in shared deployments.
- Store source media and large derived artifacts behind an object-store interface,
  implemented by the local filesystem and an S3-compatible service.
- Store dense tracking observations as immutable, partitioned Parquet and query them
  with DuckDB or Polars.
- Keep raw inputs and published dataset versions immutable. Store opaque object keys
  rather than public URLs or user-controlled paths.

## Consequences

The local profile needs no infrastructure service, while deployed storage can scale
independently. Application ports must hide database and object-store differences.
Cross-store writes cannot rely on distributed transactions, so publishing uses
staged objects, checksums, and explicit dataset status transitions.

