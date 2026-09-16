# AGENTS.md

## Purpose

This file defines repository-wide instructions for coding agents and contributors
working on Tribuna.

Tribuna is a demonstration and research tool for football analysis. Its primary
experience combines tactical-camera video with synchronized overlays and optional
analytical views such as a pitch radar, Voronoi regions, heatmaps, events, and
derived metrics.

The project is currently in its architecture/bootstrap phase. Do not assume the
target application structure already exists.

## Sources of truth

Read these documents before making architectural or data-model changes:

1. `README.md` for the project entry point and currently available commands.
2. `docs/architecture.md` for the proposed architecture, data contracts, folder
   structure, and implementation roadmap.
3. Migration files and versioned schemas, once introduced, for implemented database
   and interchange contracts.

If documentation and executable behavior disagree, identify the mismatch. Do not
silently change a public contract to make a test pass.

Consequential design changes should include an Architecture Decision Record under
`docs/adr/` and an update to affected documentation.

## Current repository state

The repository contains a Python uv workspace and a private pnpm workspace. The
supported contributor workflow is:

```bash
make bootstrap
make generate
make dev
make check
```

`apps/backend` implements the packaged FastAPI health API. `apps/web` implements the
React health shell and consumes checked-in types generated from OpenAPI. Persistence,
media APIs, a worker, Playwright, and Docker Compose remain future work; do not claim
those workflows exist until implemented and verified.

The repository targets Python 3.12. Keep `.python-version`, `requires-python`, Ruff,
CI, and the lock file aligned to that minor line unless an explicit compatibility
decision changes it. It also targets Node.js 24 LTS and pnpm 12.4.2 through
Corepack; keep `.nvmrc`, `packageManager`, CI, and `pnpm-lock.yaml` aligned.

## Architectural direction

Start with a modular monolith:

- React and TypeScript for the browser application.
- FastAPI and Python for HTTP APIs and application use cases.
- A separate worker process, built from the same backend codebase, for imports,
  media processing, computer vision, and expensive analysis.
- SQLite and local files for the zero-configuration development profile.
- PostgreSQL and S3-compatible object storage for shared deployments.
- Parquet for dense tracking observations, queried with DuckDB or Polars.

Do not introduce microservices, Kafka, Redis, Kubernetes, PostGIS, or a dedicated
time-series database without a measured requirement and a recorded decision.

Keep deployable simplicity without sacrificing internal boundaries:

- `domain` contains entities, value objects, rules, and domain errors. It must not
  import FastAPI, SQLAlchemy, OpenCV, or storage SDKs.
- `application` contains use cases and interfaces for repositories, storage, jobs,
  and importers.
- inbound adapters expose HTTP, CLI, or worker entry points.
- outbound adapters implement persistence, object storage, Parquet access, and
  provider imports.
- analytics functions consume canonical typed inputs and return versioned results.

Do not put domain behavior in route handlers, ORM models, UI components, or generic
utility modules.

## Data ownership and storage

Use each store for its intended workload:

- Relational database: projects, matches, periods, teams, rosters, media metadata,
  timeline maps, calibrations, datasets, events, annotations, jobs, and analysis-run
  metadata.
- Parquet: dense player, ball, referee, and unknown-entity tracking observations.
- Object/file storage: source video, raw imports, Parquet datasets, thumbnails,
  rendered exports, and large derived artifacts.

Raw inputs and published datasets are immutable. Corrections create a new version
with explicit parentage and provenance. Never overwrite raw observations with
smoothed, normalized, or interpolated values.

Store opaque object keys in the database, not public URLs or trusted filesystem
paths. Never derive a path directly from an uploaded filename.

Keep frequently queried fields typed. JSON is appropriate for bounded parameters,
provenance, or provider-specific qualifiers, not as a substitute for the core
schema.

## Time contract

Time synchronization is a core domain concern.

- Persist time as integer microseconds using names ending in `_us`.
- Use half-open intervals: `[start_us, end_us)`.
- Treat presentation timestamps as authoritative for video synchronization.
- Do not calculate time as `frame_number / nominal_fps` for variable-frame-rate
  media.
- Map media time to match time through explicit, potentially piecewise timeline
  segments.
- Retain source timestamps and frame numbers for provenance.
- Preserve missing samples as gaps unless interpolation is explicitly requested.
- Any interpolation must declare its method and maximum permitted gap.

Use one playback clock in the frontend. Video overlays, pitch radar, timelines, and
analytical panels must not maintain independent timers.

## Coordinate contract

- Canonical pitch units are metres.
- Canonical origin is the bottom-left of the physical pitch in source orientation.
- `x` follows pitch length and `y` follows pitch width.
- Use the match's configured pitch dimensions; never assume 105 x 68 metres.
- Store team attacking direction per period.
- Direction-normalized coordinates are derived views and must not replace canonical
  source-orientation coordinates.
- Image coordinates are pixels from the image's top-left corner.
- Calibration versions must define transform direction, validity range, method,
  control points, and reprojection error.

Do not silently clamp out-of-bounds observations. Retain them and attach a validation
or quality flag.

## API and frontend rules

- Version public endpoints under `/api/v1`.
- Use stable machine-readable error codes and include request identifiers.
- Paginate metadata collections and window time-series queries.
- Never make one network request per video frame.
- Prefer direct, range-capable video delivery or signed object URLs over decoding
  frames in the API.
- Generate frontend API types from OpenAPI once that workflow exists.
- Validate external data and real-time messages at runtime.
- Keep server state in the query cache and transient playback/UI state in a small
  dedicated store.
- Use WebGL/canvas for objects updated every animation frame. DOM or SVG remains
  suitable for controls, labels, and small static charts.
- Gate each visualization by explicit data capabilities. Missing data should produce
  an unavailable state with a reason, not a runtime failure.

## Importers and analytics

Provider-specific formats stop at importer boundaries. Importers must:

- preserve immutable raw inputs;
- validate before publishing;
- normalize identifiers, time, units, coordinates, and orientation;
- emit the versioned canonical contract;
- report structured warnings and errors;
- record importer name, version, parameters, and source checksum;
- be idempotent for equivalent inputs and parameters.

Analysis results must record input dataset/calibration versions, normalized
parameters, algorithm version, code revision, warnings, and output checksum.

Document units and methodology for every derived metric and visualization. Do not
present interpolation, smoothing, confidence estimates, or model output as observed
fact.

## Coding standards

### Python

- Use type annotations for public functions and application boundaries.
- Prefer small, explicit modules over generic `utils.py` or `helpers.py` files.
- Keep I/O at adapters so domain and analytics code can be tested deterministically.
- Prefer pure functions for geometry, time mapping, and numerical transformations.
- Use timezone-aware UTC timestamps for audit data.
- Catch specific exceptions at the boundary that can handle them; preserve causal
  context when translating errors.
- Use Ruff for linting and formatting. Add static type checking when the backend
  workspace is established.

### TypeScript

- Enable strict TypeScript settings.
- Avoid `any`; validate unknown external values before narrowing them.
- Co-locate feature components, hooks, tests, and types under their feature.
- Keep render-loop objects and frequently changing playback state out of React
  component state when that would trigger full-tree rerenders.
- Keep coordinate transforms in shared, tested graphics/domain modules rather than
  duplicating formulas across visualizations.

### General

- Prefer clear domain names such as `match_time_us` and `pitch_length_m` over terse
  abbreviations.
- Include units in field names where ambiguity is possible.
- Do not commit secrets, source footage, large datasets, generated artifacts, or
  personal data.
- Avoid speculative abstractions. Introduce an interface when it protects a real
  boundary or has more than one required implementation profile.
- Keep scripts as thin orchestration; domain logic belongs in tested packages.

## Testing requirements

Match verification effort to the risk of the change.

- Domain behavior: focused unit tests.
- Time and coordinate transforms: golden examples, boundary cases, and property
  tests for invertibility where appropriate.
- Importers: canonical contract tests plus malformed and idempotency fixtures.
- SQL or migrations: integration tests against real supported databases.
- Parquet and media boundaries: a small number of tests using real fixture files,
  not mocks of the underlying formats.
- API changes: request/response tests and OpenAPI contract verification.
- Frontend behavior: component tests; Playwright for critical user journeys.
- Visual changes: deterministic known-frame assertions and a limited number of
  tolerant screenshots.
- Bugs involving time, coordinates, or provider data must add a regression fixture.

The first representative end-to-end path is:

```text
create match -> upload video -> import tracking -> map time -> calibrate
-> seek/play with overlay -> open radar/Voronoi/heatmap -> export provenance
```

## Working practices

Before editing:

1. Inspect the relevant implementation, tests, and documentation.
2. Check the worktree and preserve unrelated user changes.
3. Identify whether the change affects a canonical data or API contract.

While editing:

1. Implement the smallest complete vertical slice.
2. Keep domain, application, and adapter concerns separated.
3. Update tests and documentation alongside behavior.
4. Avoid unrelated cleanup or dependency upgrades.

Before handing off:

1. Run the narrow tests for the changed behavior.
2. Run the repository's available lint, format, type, and test checks.
3. Verify documented commands actually exist before advertising them.
4. Report what changed, what was verified, and any remaining limitation.

## Definition of done

A change is complete when:

- the requested behavior is implemented rather than only scaffolded;
- relevant automated tests pass;
- time, coordinate, provenance, and missing-data behavior is explicit;
- schema/API changes are versioned or migrated safely;
- documentation matches the implementation;
- no secrets, large generated files, or licensed match assets were added;
- failure and unavailable-data states are usable and observable.
