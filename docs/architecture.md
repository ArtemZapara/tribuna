# Tribuna architecture blueprint

- Status: proposed
- Audience: maintainers, football analysts, and research collaborators
- Last updated: 2026-09-11

## 1. Executive summary

Tribuna is an analysis workspace for synchronized football video and structured
football data. Its primary screen is a video player with time-aligned tactical
overlays. Supporting panels can show a top-down pitch, Voronoi regions, heatmaps,
events, and derived metrics when the required source data exists.

The recommended starting point is a **modular monolith**, not a collection of
microservices:

- a React/TypeScript browser application for playback and interactive graphics;
- a FastAPI/Python application for metadata, imports, queries, and analysis APIs;
- a separate Python worker process, built from the same codebase, for CPU-heavy or
  long-running jobs;
- SQLite for a zero-configuration local demo, with PostgreSQL as the shared or
  production database;
- local files for a local demo, with S3-compatible object storage as the deployment
  option;
- Parquet for dense tracking observations and DuckDB/Polars for analytical scans.

This is deliberately a two-process system (API plus worker) with one frontend.
Module boundaries and ports for storage and jobs make later extraction possible,
but the project should not pay the operational cost of microservices before the
workload proves that they are needed.

## 2. Scope and architectural drivers

### 2.1 MVP capabilities

The first useful demonstration should support:

1. Create a match and upload one tactical-camera MP4.
2. Import tracking data from a documented CSV or JSON format.
3. Map video time to match time and calibrate image pixels to pitch coordinates.
4. Play, pause, seek, and step through video while drawing player and ball markers.
5. Show a synchronized 2D pitch radar.
6. Toggle Voronoi regions and a simple player/team heatmap.
7. Filter by team/player/time range and inspect basic data-quality warnings.

The application must remain useful when some data is absent. Capabilities are
derived from available assets rather than assumed. A video-only match still plays;
a tracking-only dataset can still render a pitch animation; calibration-dependent
video overlays remain disabled until calibration exists.

### 2.2 Explicit non-goals for the first release

- Automatic player detection, re-identification, or jersey-number recognition.
- Multi-camera stitching.
- Low-latency live broadcast production.
- A universal importer for every commercial data vendor.
- Predictive models presented as validated sporting conclusions.
- Multi-tenant billing or a full identity platform.

These are future adapters or bounded modules, not assumptions embedded in the MVP.

### 2.3 Quality attributes

| Attribute | Initial target | Design response |
| --- | --- | --- |
| Prototype speed | One-command local start after bootstrap | SQLite, local object store, seeded demo data |
| Extensibility | Add a visualization or data provider without changing core models | Canonical contracts, importer and analysis plugin protocols |
| Playback correctness | Overlay within one source frame of the selected video time | Explicit time mapping, source PTS, nearest-frame lookup |
| Interactive performance | Smooth playback at 25/30 fps on a normal laptop | Draw with a GPU-backed renderer, fetch tracking in chunks, no per-frame REST calls |
| Reproducibility | Every derived result identifies inputs, parameters, and code version | Immutable source assets and versioned analysis runs |
| Portability | Local laptop and container deployment use the same application | Storage and job-runner interfaces; environment-based configuration |
| Research integrity | Units, coordinate systems, missingness, and confidence are explicit | Versioned schemas and validation reports; no silent interpolation |

## 3. Recommended technology stack

Versions should be pinned in lock files during milestone 1 rather than copied from
this document.

### 3.1 Frontend

- **React + TypeScript + Vite**: application shell and fast development loop.
- **PixiJS**: WebGL/WebGPU-backed scene graph for video overlays and the pitch radar.
  DOM/SVG is acceptable for labels and small static charts, but not for objects
  updated every animation frame.
- **TanStack Query**: server-state fetching, cancellation, and cache management.
- **Zustand or a small reducer**: playback/UI state only; do not duplicate API data.
- **Apache ECharts**: aggregate plots such as time series and heatmap legends.
- **Zod**: runtime validation at external data boundaries and WebSocket messages.
- **Vitest + React Testing Library + Playwright**: unit, component, and end-to-end
  tests.

### 3.2 Backend and analytics

- **Python 3.12** initially. The repository pins this minor line for reproducible
  scientific and computer-vision package support. Re-evaluate newer runtimes only
  after all binary dependencies support them.
- **FastAPI + Pydantic**: typed HTTP/OpenAPI endpoints and optional WebSocket job
  notifications.
- **SQLAlchemy 2 + Alembic**: portable relational persistence and migrations.
- **Polars + NumPy + SciPy**: columnar transforms and numerical algorithms.
- **PyArrow + Parquet**: stable, interoperable storage for dense tracking samples.
- **DuckDB**: embedded analytical queries over Parquet without a separate analytics
  service.
- **OpenCV**: calibration, geometry, and frame-oriented computer vision.
- **FFmpeg/ffprobe** as a system dependency: media probing, normalization,
  thumbnails, and optional HLS renditions.
- **pytest, Hypothesis, Ruff, and mypy/pyright**: automated quality checks.

FastAPI supports both WebSockets and post-response background tasks, but substantial
video or analytics work must run in the worker process rather than in an API worker.
DuckDB can query Parquet directly and push filters/projections into scans, which is
why it is a good local analytical layer for time/player-window queries.

### 3.3 Infrastructure profiles

| Concern | Local prototype | Shared/deployed |
| --- | --- | --- |
| Metadata | SQLite | PostgreSQL |
| Video/artifacts | `data/` filesystem | S3-compatible storage |
| Dense tracking | Local partitioned Parquet | Object-store Parquet |
| Jobs | DB-backed single worker | DB-backed workers initially; introduce a queue only if measured load requires it |
| Video delivery | HTTP range requests for MP4 | Object-store/CDN signed URLs; HLS if needed |
| Authentication | Disabled/local identity | OIDC provider and project-level authorization |
| Packaging | `uv` + `pnpm` | Containers, then Compose or an orchestrator |

Avoid Redis, Kafka, Kubernetes, PostGIS, and a time-series database in the first
prototype unless a demonstrated requirement needs them.

## 4. System architecture

```text
                         +-------------------------------+
                         | React analysis workspace      |
                         | video | overlay | pitch | UI  |
                         +---------------+---------------+
                                         |
                     REST (metadata/chunks) | WS/SSE (job progress only)
                                         v
+------------------+       +-------------+-----------------------------+
| MP4 / HLS / CDN  |<------+ FastAPI modular monolith                  |
| byte-range media | URL   |                                           |
+------------------+       | matches | media | tracking | events       |
                           | analysis | annotations | imports           |
                           +------+--------------------+----------------+
                                  |                    |
                       metadata   |                    | enqueue/claim
                                  v                    v
                           +------+-----+       +------+---------------+
                           | SQLite /  |       | Python worker         |
                           | PostgreSQL|       | import/CV/analytics   |
                           +------+-----+       +------+---------------+
                                  |                    |
                                  | references         | read/write
                                  v                    v
                           +------+--------------------+---------------+
                           | Storage abstraction                       |
                           | raw video | Parquet | thumbnails | results|
                           | local filesystem or S3-compatible store   |
                           +--------------------------------------------+
```

### 4.1 Backend module boundaries

The modules live in one Python package, but dependencies point inward:

- **domain**: entities, value objects, coordinate/time rules, and errors; no FastAPI,
  SQLAlchemy, OpenCV, or object-store imports.
- **application**: use cases and ports such as `MatchRepository`, `ObjectStore`,
  `TrackingStore`, and `JobRunner`.
- **adapters/inbound**: HTTP routes, CLI commands, and worker entry points.
- **adapters/outbound**: SQLAlchemy repositories, filesystem/S3 storage, DuckDB
  queries, and provider-specific importers.
- **analytics**: pure, testable transformations accepting canonical arrays/tables
  and returning versioned results.

Modules must communicate through application services or typed contracts, not by
reaching into one another's database tables. Do not create a generic `utils.py`;
put shared concepts in named modules such as `coordinates.py` or `timebase.py`.

### 4.2 Frontend composition

The main route, `/matches/:matchId/analysis`, owns a single `PlaybackClock`:

- `VideoStage` exposes the browser video's current media time.
- `OverlayStage` draws image-space items for the selected tracking frame.
- `PitchRadar` draws the same canonical frame in pitch coordinates.
- `Timeline` shows periods, events, annotations, and data gaps.
- `InspectorPanel` hosts opt-in analytics such as Voronoi and heatmaps.

All synchronized views subscribe to the playback clock. They do not maintain
independent timers. On every browser animation frame, the clock maps media time to
match time and selects the nearest available tracking observation from an in-memory
chunk.

### 4.3 Visualization capability contract

Each visualization declares its data requirements:

```ts
type Capability =
  | "video"
  | "tracking.pitch_coordinates"
  | "tracking.image_coordinates"
  | "ball_tracking"
  | "events"
  | "camera_calibration";

type VisualizationDefinition = {
  id: string;
  requires: Capability[];
  renderer: "overlay" | "pitch" | "panel";
};
```

The API returns match capabilities and reasons for unavailable capabilities. The UI
hides or disables a visualization predictably rather than failing on null data.

## 5. Data flow

### 5.1 Import and preparation

```text
Upload/register asset
  -> checksum and immutable raw-object record
  -> ffprobe/provider-specific inspection
  -> validation report (errors, warnings, coverage)
  -> canonicalization (units, IDs, orientation, timestamps)
  -> metadata transaction + partitioned Parquet write
  -> derived capability refresh
  -> enqueue thumbnails/calibration/analysis jobs
  -> publish job status
```

An import is idempotent on `(content checksum, importer name, importer version,
parameters)`. Raw inputs are never overwritten. A failed import retains its report
and can be retried with corrected mapping parameters.

### 5.2 Playback query path

1. The page loads match metadata, periods, assets, capabilities, and timeline maps.
2. The browser receives a direct/range-capable media URL; the API does not decode or
   send individual video frames.
3. The client requests a tracking window, for example `t=600000..610000`, including
   only the required entities and fields.
4. The API uses DuckDB to scan the relevant Parquet partition(s), returning a compact
   binary Arrow payload eventually; JSON is acceptable for the first slice.
5. The browser keeps the current and next window in memory. A seek cancels stale
   requests and fetches around the new time.
6. `requestAnimationFrame` reads `video.currentTime`, maps it through the selected
   timeline segment, and renders the nearest sample. Gaps remain gaps unless the user
   explicitly enables bounded interpolation.

Do not make one API call per video frame and do not burn overlays into the source
video for the interactive workspace. A rendered export can be a separate job.

### 5.3 Analysis job path

1. `POST /analysis-runs` validates parameters, records input dataset versions, and
   inserts a queued job.
2. The worker atomically claims the job and updates heartbeat/progress.
3. The algorithm reads a bounded Parquet scan, calculates a deterministic result,
   and writes an artifact or small metric rows.
4. The worker records code version, algorithm version, parameters, output checksum,
   warnings, and final status.
5. The UI receives progress through polling first, then SSE/WebSocket if useful, and
   invalidates the relevant query when complete.

Cancellation is cooperative. A stale running job is recoverable using its heartbeat,
and retry policy is explicit rather than infinite.

### 5.4 Live-data evolution

Live operation should be a later adapter:

```text
RTSP/camera -> FFmpeg/GStreamer -> HLS segments + source timestamps
tracking provider -> canonical message adapter -> short rolling buffer
rolling buffer -> WebSocket client chunks + durable Parquet micro-batches
```

The canonical playback clock and entity contracts remain the same. "Live" is a
moving time window, not a second analysis domain.

## 6. Time and coordinate contracts

These rules are more important than the choice of plotting library.

### 6.1 Time

- Persist integer microseconds (`*_us`) for source PTS and the canonical match
  timeline. Avoid floating-point seconds in stored data.
- A `timeline_segment` maps source media PTS to match time using an affine mapping.
  Multiple segments support halftime, stoppages, clipped video, and discontinuities.
- Retain provider timestamps and source frame numbers as provenance; neither is the
  universal join key.
- Store the media stream time base reported by ffprobe. Variable-frame-rate media
  must use presentation timestamps, not `frame_number / nominal_fps`.
- Each tracking sample has a quality flag and may be absent. Interpolation must state
  its maximum gap and method.

### 6.2 Pitch coordinates

- Canonical unit: metres.
- Canonical origin: bottom-left of the physical pitch in the source orientation.
- `x` follows pitch length and `y` follows pitch width.
- Store actual `pitch_length_m` and `pitch_width_m`; do not assume every pitch is
  105 x 68 m.
- Store `attacking_direction` by team and period. Direction-normalized views are
  query/render transformations and must not replace raw canonical coordinates.
- Image coordinates use pixels with origin at the image top-left.
- A calibration version contains the homography from pitch plane to image plane,
  lens/distortion metadata when relevant, validity time range, control points, and
  reprojection error.

The ball may have `z_m`; players normally lie on the pitch plane. A player or ball
outside the pitch bounds should be retained with a quality warning, not silently
clamped.

## 7. Core database schema and data models

Use UUIDv7 (or application-generated UUIDs) for durable public IDs and UTC timestamps
for audit fields. The following is a logical schema; migration files are the eventual
source of truth.

### 7.1 Relational metadata

#### `projects`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Analysis workspace/tenant boundary |
| `name` | text | Required |
| `created_at`, `updated_at` | timestamptz | UTC |

#### `matches`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `project_id` | UUID FK | Indexed |
| `name` | text | Human-readable title |
| `competition`, `season`, `venue` | text nullable | Descriptive metadata |
| `kickoff_at` | timestamptz nullable | |
| `pitch_length_m`, `pitch_width_m` | decimal | Positive |
| `status` | enum | `draft`, `ready`, `archived` |
| `created_at`, `updated_at` | timestamptz | |

#### `periods`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `match_id` | UUID FK | |
| `number` | smallint | Unique per match |
| `kind` | enum | first half, second half, extra time, penalties, other |
| `start_match_us`, `end_match_us` | bigint | Check end > start |

#### `teams`, `players`, and `match_roster_entries`

- `teams`: `id`, `name`, `short_name`, optional colors.
- `players`: `id`, provider-independent display identity and optional metadata.
- `match_teams`: match/team role (`home`, `away`, `official/other`) and per-period
  attacking direction.
- `match_roster_entries`: match, team, player, shirt number, starter flag, and
  optional active intervals. Do not put match-specific shirt numbers on `players`.

#### `media_assets`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `match_id` | UUID FK | |
| `kind` | enum | video, image, thumbnail, rendered export |
| `storage_key` | text | Opaque key, never a public URL |
| `original_filename`, `mime_type` | text | |
| `size_bytes`, `sha256` | bigint/text | Unique checksum as appropriate |
| `duration_us` | bigint nullable | |
| `width`, `height` | integer nullable | |
| `codec`, `container`, `time_base` | text nullable | Probe metadata |
| `status` | enum | uploading, probing, ready, failed |
| `created_at` | timestamptz | |

#### `timeline_segments`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `media_asset_id`, `period_id` | UUID FK | |
| `source_start_us`, `source_end_us` | bigint | Media PTS range |
| `match_start_us`, `match_end_us` | bigint | Canonical time range |
| `mapping_kind` | enum | `linear`, initially |
| `confidence` | float nullable | 0..1 |

Segments must not overlap within one media asset. Keep explicit endpoints even when
the normal mapping has slope 1.

#### `calibrations`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Immutable version |
| `media_asset_id` | UUID FK | |
| `valid_from_us`, `valid_to_us` | bigint | Source PTS range |
| `method`, `algorithm_version` | text | manual, automatic, imported |
| `homography` | JSON | Nine finite numbers with defined direction |
| `control_points` | JSON | Pitch/image pairs and labels |
| `reprojection_error_px` | float nullable | Quality signal |
| `created_at` | timestamptz | |

#### `datasets` and `data_sources`

`data_sources` records an uploaded file/provider and its checksum. `datasets`
records the canonical product:

- `id`, `match_id`, `source_id`;
- `kind`: tracking, events, derived;
- `schema_version`, importer name/version, parameter JSON;
- coverage start/end, nominal sample rate, entity count;
- `storage_key`, checksum, row count, status;
- validation summary and creation timestamp.

Published dataset versions are immutable. Re-import creates a new version and can
mark it active for a match.

#### `events`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `dataset_id`, `match_id`, `period_id` | UUID FK | |
| `match_time_us` | bigint | Indexed with match |
| `type` | text | Controlled vocabulary plus schema version |
| `team_id`, `player_id` | UUID nullable | |
| `x_m`, `y_m`, `end_x_m`, `end_y_m` | decimal nullable | Canonical coordinates |
| `outcome` | text nullable | |
| `qualifiers` | JSON | Provider-specific values under a namespace |
| `source_event_id` | text nullable | Provenance/idempotency |

Keep commonly filtered fields typed; do not hide the entire event in JSON.

#### `annotations`

Analyst-authored findings are separate from provider events: `id`, `match_id`,
`author_id`, optional `period_id`, start/end match time, optional pitch geometry,
category, text, tags, optimistic-lock `revision`, and audit timestamps.

#### `analysis_runs` and `analysis_artifacts`

`analysis_runs` includes:

- analysis type and algorithm version;
- input dataset IDs and calibration ID;
- normalized parameter JSON and a deterministic cache key;
- status, progress, error summary, queued/started/finished timestamps;
- code revision and environment metadata.

`analysis_artifacts` includes run ID, kind, schema version, storage key, media type,
checksum, size, and a small JSON summary. Large grids, arrays, images, or frame-wise
outputs belong in object storage, not a relational JSON column.

#### `jobs` and `import_runs`

`jobs` is operational state: type, payload reference, status, priority, attempts,
lease owner/expiry, heartbeat, progress, error, and timestamps. `import_runs` captures
field mappings plus structured validation errors and warnings. Domain results remain
separate from transient execution state.

### 7.2 Tracking Parquet contract

Dense observations should not be one relational row per player per frame. At 25 Hz,
22 players alone produce about two million rows per match before ball and officials.

Store a long-form canonical table, partitioned by `match_id`, `dataset_id`, and
`period`, then sorted by `match_time_us`, `entity_type`, `entity_id`:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | string | yes | Contract version |
| `match_id`, `dataset_id` | string/UUID | yes | Provenance |
| `period` | int8 | yes | Period number |
| `match_time_us` | int64 | yes | Canonical clock |
| `source_time_us` | int64 | no | Original provider clock/PTS |
| `frame_number` | int64 | no | Provider/source frame number |
| `entity_type` | dictionary string | yes | player, ball, official, unknown |
| `role` | dictionary string | no | outfield_player, goalkeeper, referee, assistant_referee, other |
| `entity_id` | string/UUID | no | Null only for unresolved identity |
| `team_id` | string/UUID | no | |
| `x_m`, `y_m`, `z_m` | float32 | x/y yes | Physical coordinates |
| `vx_mps`, `vy_mps`, `speed_mps` | float32 | no | Derived or provider-supplied |
| `image_x_px`, `image_y_px` | float32 | no | Only if supplied/derived for this camera |
| `visible`, `in_play` | boolean | no | Distinct meanings |
| `confidence` | float32 | no | 0..1 |
| `quality_flags` | uint32 | yes | Versioned bit mask |

Record whether velocity is raw or derived in dataset metadata. Provider-specific
fields should live in a separately versioned raw dataset rather than continually
widening the canonical contract.

### 7.3 Derived data policy

- **Voronoi**: compute for the current frame in the browser or API because it is
  cheap and parameter-sensitive; cache only exports or expensive sequences.
- **Heatmaps**: aggregate from Parquet for a player/team/time/filter tuple; cache by
  dataset checksum plus normalized parameters.
- **Distance/speed summaries**: persist small, frequently requested results as
  versioned metrics after methodology is stable.
- **Rendered overlays**: immutable media artifacts tied to an analysis run.
- Never overwrite raw observations with smoothed or imputed values. Produce a new
  derived dataset that references its parent.

## 8. API surface

Use `/api/v1` from the first public endpoint. Representative routes:

```text
GET    /api/v1/health
GET    /api/v1/projects/{project_id}/matches
POST   /api/v1/matches
GET    /api/v1/matches/{match_id}
GET    /api/v1/matches/{match_id}/capabilities

POST   /api/v1/matches/{match_id}/media/uploads
POST   /api/v1/media/{media_id}/complete
GET    /api/v1/media/{media_id}/playback

POST   /api/v1/matches/{match_id}/imports
GET    /api/v1/imports/{import_id}
POST   /api/v1/imports/{import_id}/publish

GET    /api/v1/matches/{match_id}/tracking?from_us=&to_us=&fields=&entities=
GET    /api/v1/matches/{match_id}/events?from_us=&to_us=&types=
GET    /api/v1/matches/{match_id}/timeline

POST   /api/v1/analysis-runs
GET    /api/v1/analysis-runs/{run_id}
POST   /api/v1/analysis-runs/{run_id}/cancel
GET    /api/v1/analysis-runs/{run_id}/artifacts

POST   /api/v1/matches/{match_id}/annotations
PATCH  /api/v1/annotations/{annotation_id}
DELETE /api/v1/annotations/{annotation_id}
```

API rules:

- Use half-open time intervals `[from_us, to_us)` consistently.
- Paginate metadata collections; window time-series data.
- Return stable machine-readable error codes plus a request ID.
- Use optimistic concurrency for analyst edits.
- Generate the TypeScript client/types from OpenAPI to prevent contract drift.
- Return signed/direct playback URLs, never host filesystem paths.
- Negotiate Arrow IPC later for large tracking windows; keep JSON as the debuggable
  MVP contract.

## 9. Project folder and file structure

```text
tribuna/
├── README.md
├── pyproject.toml                 # uv workspace/tooling policy
├── uv.lock
├── package.json                   # shared JS scripts; optional pnpm workspace root
├── pnpm-workspace.yaml
├── .env.example
├── .editorconfig
├── .pre-commit-config.yaml
├── Makefile                       # thin, discoverable developer commands
├── apps/
│   ├── backend/
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── src/tribuna/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── domain/
│   │   │   │   ├── matches.py
│   │   │   │   ├── media.py
│   │   │   │   ├── tracking.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── coordinates.py
│   │   │   │   └── timebase.py
│   │   │   ├── application/
│   │   │   │   ├── commands/
│   │   │   │   ├── queries/
│   │   │   │   ├── dto.py
│   │   │   │   └── ports/
│   │   │   ├── adapters/
│   │   │   │   ├── api/
│   │   │   │   │   ├── app.py
│   │   │   │   │   ├── dependencies.py
│   │   │   │   │   ├── errors.py
│   │   │   │   │   └── routes/
│   │   │   │   ├── cli/
│   │   │   │   ├── persistence/
│   │   │   │   │   ├── models.py
│   │   │   │   │   ├── repositories.py
│   │   │   │   │   └── session.py
│   │   │   │   ├── importers/
│   │   │   │   │   ├── base.py
│   │   │   │   │   └── canonical_csv.py
│   │   │   │   ├── storage/
│   │   │   │   │   ├── filesystem.py
│   │   │   │   │   ├── s3.py
│   │   │   │   │   └── tracking_parquet.py
│   │   │   │   └── jobs/
│   │   │   ├── analytics/
│   │   │   │   ├── geometry.py
│   │   │   │   ├── heatmaps.py
│   │   │   │   ├── kinematics.py
│   │   │   │   └── validation.py
│   │   │   └── observability.py
│   │   └── tests/
│   │       ├── unit/
│   │       ├── integration/
│   │       ├── contract/
│   │       └── fixtures/
│   ├── worker/
│   │   ├── pyproject.toml         # optional thin executable over tribuna package
│   │   ├── src/tribuna_worker/
│   │   │   ├── main.py
│   │   │   └── handlers.py
│   │   └── tests/
│   └── web/
│       ├── package.json
│       ├── vite.config.ts
│       ├── playwright.config.ts
│       ├── public/
│       └── src/
│           ├── app/               # router, providers, shell
│           ├── api/               # generated client and query keys
│           ├── features/
│           │   ├── match-browser/
│           │   ├── playback/
│           │   ├── video-overlay/
│           │   ├── pitch-radar/
│           │   ├── timeline/
│           │   ├── heatmaps/
│           │   ├── voronoi/
│           │   ├── annotations/
│           │   └── imports/
│           ├── components/        # genuinely shared UI components
│           ├── graphics/          # Pixi primitives and transforms
│           ├── state/             # playback/UI state
│           ├── types/
│           └── test/
├── packages/
│   ├── data-contracts/
│   │   ├── README.md
│   │   ├── tracking.schema.json
│   │   ├── events.schema.json
│   │   └── examples/
│   └── sample-inputs/             # provenance only; no third-party media
├── docs/
│   ├── architecture.md
│   ├── adr/
│   ├── data-formats/
│   └── research-methods/
├── infra/
│   ├── compose.yaml
│   └── docker/
├── scripts/                       # orchestration only, no domain logic
├── data/                          # ignored local runtime data
│   ├── raw/
│   ├── canonical/
│   ├── derived/
│   └── demo/
└── tests/
    └── e2e/                       # cross-application scenarios
```

The worker may initially be an entry point in the backend package rather than a
separate package. Split it only when its dependency set or deployment lifecycle is
meaningfully different. Similarly, do not create a separate Python package for each
domain module until independent reuse or release cadence justifies it.

## 10. Implementation roadmap

Each milestone ends in a demonstrable behavior and automated acceptance checks.

### Milestone 0 — decisions and sample contract (1–2 days)

- Commit this architecture and short ADRs for storage, coordinate system, and
  timeline mapping.
- Document a tactical-camera sample source and provide an offline builder that turns
  an authorized local copy into a normalized 40-second, video-only fixture beginning
  at source time 02:40 while preserving its coded resolution. Do not redistribute
  the source media.
- Define the canonical tracking CSV/Parquet schema with independent synthetic
  examples; do not imply that they describe the sample video.
- Pin the repository, tooling, and CI to the selected Python 3.12 line.

**Done when:** CI validates the contract and media builder entirely offline using
synthetic inputs; a developer with an authorized local copy can produce a 40-second
sample with checksummed provenance and explicit source/media-time boundaries.
Tracking, match-time, and coordinate mappings for that video are out of scope.

### Milestone 1 — repository foundation (2–3 days)

- Establish the `apps/backend` and `apps/web` workspaces.
- Add configuration validation, structured logging, health endpoint, linting, type
  checks, unit test runners, and CI.
- Add `.env.example` and thin `make bootstrap`, `make dev`, and `make check` targets.
- Generate frontend API types from a trivial OpenAPI endpoint.

**Done when:** a clean clone can bootstrap, run both apps, open a health page, and
pass all checks using documented commands.

### Milestone 2 — match and media vertical slice (3–5 days)

- Create initial migrations for projects, matches, periods, and media assets.
- Implement match create/list/detail endpoints and a minimal match browser.
- Upload/register MP4, compute SHA-256, probe with ffprobe, and serve a byte-range or
  signed playback URL.
- Display duration/resolution/codec and failure diagnostics.

**Done when:** an integration test creates a match and uploads a fixture; Playwright
opens it, plays, pauses, and seeks; duplicate upload behavior is deterministic.

### Milestone 3 — canonical tracking import (4–6 days)

- Implement the canonical CSV importer behind an importer protocol.
- Validate identifiers, monotonic time, finite coordinates, bounds, duplicates,
  missingness, and coverage.
- Write immutable, partitioned Parquet plus dataset metadata and validation report.
- Add preview/publish/retry states and import UI.

**Done when:** a golden import round-trips exactly; malformed fixtures produce stable
error codes; importing the same source twice is idempotent.

### Milestone 4 — synchronized playback and overlay (5–8 days)

- Implement timeline-segment editing and mapping functions.
- Add windowed tracking endpoint and client prefetch/cache.
- Build the single playback clock and Pixi overlay for players, ball, labels, and
  trails.
- Surface data gaps and drift diagnostics.

**Done when:** deterministic browser tests at known seek positions place markers
within a defined tolerance; no per-frame network requests occur during normal play.

### Milestone 5 — calibration and pitch radar (4–7 days)

- Implement a manual four-or-more-point calibration flow and homography validation.
- Version calibrations with validity ranges and reprojection error.
- Draw a configurable-size pitch and synchronized entities.
- Add team colors, selected-player focus, orientation toggle, and coordinate debug
  mode.

**Done when:** golden control points round-trip pitch-to-image-to-pitch within the
tolerance; invalid/degenerate calibrations are rejected; radar and overlay share the
same selected frame.

### Milestone 6 — first analytical panels (4–7 days)

- Add per-frame Voronoi clipped to pitch bounds, with duplicate/missing-position
  handling.
- Add player/team heatmap with explicit bin size, smoothing, normalization, and time
  filter parameters.
- Add capability gating, legends, methodology text, and cached analysis results.

**Done when:** geometry and heatmap golden tests pass; changing a parameter changes
the cache key; a match lacking required data shows an explanation rather than an
error.

### Milestone 7 — durable jobs and reproducibility (3–5 days)

- Run import and analysis work in the separate worker.
- Add atomic claims, leases/heartbeats, cooperative cancellation, bounded retries,
  and progress reporting.
- Record input checksums, algorithm/code versions, parameters, outputs, and timings.
- Test worker death and stale-job recovery.

**Done when:** the API remains responsive during a heavy fixture; killed jobs recover
or fail predictably; identical analysis requests reuse a verified artifact.

### Milestone 8 — research and analyst workflow (4–7 days)

- Add event import, timeline markers, annotations, clips/bookmarks, and export of
  analysis parameters/results.
- Add data-quality and provenance panels.
- Write method notes for every metric and visualization.

**Done when:** a user can navigate from event to synchronized video, annotate a time
range, reload without data loss, and export a reproducibility manifest.

### Milestone 9 — deployment hardening (3–6 days)

- Run the same suite against PostgreSQL and S3-compatible storage.
- Add containers, non-root execution, upload limits, CORS/headers, backups, and
  retention settings.
- Add OpenTelemetry-compatible traces/metrics, request IDs, and health/readiness
  checks.
- Perform a threat model and data-licensing/privacy review before real match data.

**Done when:** a Compose deployment survives restart, restores from backup, rejects
invalid uploads, and meets an agreed representative-match performance budget.

### Later, evidence-driven work

- Live ingest and rolling buffers.
- Automated calibration and tracking models.
- Multi-camera/time-source synchronization.
- Collaborative editing and OIDC/RBAC.
- GPU scheduling and specialized compute workers.
- A formal analysis plugin SDK.

Only introduce these after a user workflow or measured bottleneck requires them.

## 11. Testing strategy

- **Domain unit tests:** time maps, coordinate transforms, pitch bounds, capability
  rules, and analysis algorithms. Use property tests for invertibility and edge cases.
- **Importer contract tests:** every importer must produce the same canonical fixture
  semantics and structured validation report.
- **Persistence integration tests:** real SQLite and PostgreSQL in CI for repository
  and migration behavior; real Parquet reads/writes for tracking.
- **API contract tests:** OpenAPI schema snapshots and response/error examples.
- **Visual/component tests:** render known frames and assert transforms; keep a small
  number of tolerant screenshot tests for the composed workspace.
- **End-to-end tests:** upload -> import -> calibrate -> seek -> analyze -> export.
- **Performance tests:** representative 90-minute match, cold seek latency, tracking
  window size, animation frame budget, and job peak memory.

Every bug involving time or coordinates should result in a small golden regression
fixture. Avoid mocks for FFmpeg, SQL, or Parquet in the small number of integration
tests meant to validate those boundaries.

## 12. Security, privacy, and data governance

- Accept-list media/data formats; cap sizes, rows, and decompressed output; never
  trust filenames or provider fields as paths.
- Store generated object keys and original filenames separately.
- Verify checksums and make raw assets immutable.
- Use signed, expiring object URLs in shared deployments.
- Treat player identity, biometric inference, and youth footage as potentially
  sensitive. Document lawful basis, access controls, retention, and deletion.
- Preserve source licence and attribution metadata. A convenient public video is not
  automatically licensed for redistribution or model training.
- Never deserialize arbitrary Python objects from uploads.
- Escape analyst/provider text and validate JSON qualifiers before rendering.
- Keep secrets out of `.env.example`, logs, analysis manifests, and frontend bundles.

## 13. Observability and performance budgets

Record structured logs and traces with `request_id`, `match_id`, `dataset_id`, and
`job_id` where relevant, without logging raw personal data.

Initial budgets for a representative 25 Hz match on a development laptop:

- metadata API p95 under 200 ms after warm-up;
- a 10-second, 23-entity tracking window under 500 ms cold and under 200 ms warm;
- less than 2 seconds from seek completion to visible synchronized overlays;
- sustained UI rendering near display refresh without API calls per frame;
- bounded worker memory documented per analysis type.

These are hypotheses. Capture fixtures and measurements before tightening or
redesigning the system.

## 14. Key risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Video/tracking drift | Explicit piecewise timeline maps, PTS-based tests, visible diagnostics |
| Vendor schemas leak into UI/domain | Immutable raw source plus versioned canonical importer boundary |
| Tracking volume overwhelms SQL/API | Parquet partitions, projection/window queries, client chunk prefetch |
| CV dependencies block new Python releases | Start on Python 3.12 and pin reproducible environments |
| Misleading analytical visuals | Method/version metadata, confidence and missingness indicators, research notes |
| Prototype becomes distributed too early | Modular monolith, local defaults, measured extraction criteria |
| Single DB job queue reaches limits | Encapsulated job port; adopt a broker only after concurrency/load evidence |

## 15. Decisions to validate with the first users

The architecture can proceed without answers, but early analyst interviews should
validate:

1. Uploaded prerecorded video versus live camera priority.
2. Tracking/event data providers and their licensing constraints.
3. Whether exact provider coordinates, direction-normalized coordinates, or both are
   expected in exports.
4. The maximum representative match/sample rate/entity count.
5. The first three decisions analysts want the tool to help them make.
6. Whether local/offline use is a requirement for sensitive footage.

These answers should change adapters and milestone ordering, not the canonical time,
coordinate, provenance, and module boundaries.

## 16. Reference documentation

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [FastAPI background task caveats](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [DuckDB Parquet support](https://duckdb.org/docs/stable/data/parquet/overview)
- [PixiJS renderers](https://pixijs.com/8.x/guides/components/renderers)
- [OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html)
- [Polars lazy API](https://docs.pola.rs/user-guide/lazy/using/)
