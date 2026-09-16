# Tribuna

Tribuna is a demonstration and research workspace for football analysis. It pairs
tactical-camera video with synchronized overlays and optional analytical views such
as a top-down pitch radar, Voronoi regions, heatmaps, events, and derived metrics.

> **Status:** Milestone 1 repository foundation. The FastAPI health API, React
> health shell, generated OpenAPI types, workspace tooling, and CI are implemented.
> Match persistence, media playback, tracking import, and analysis begin in later
> milestones.

The complete system design, data flow, schemas, folder structure, trade-offs, and
testable delivery roadmap are in [docs/architecture.md](docs/architecture.md).

## Product principles

- Video remains usable when tracking or event data is unavailable.
- Every overlay is tied to an explicit time map and coordinate system.
- Raw inputs are immutable; derived results retain provenance and algorithm versions.
- A local demo should run without cloud services.
- Provider formats stop at importer boundaries and become versioned canonical data.
- The project starts as a modular monolith and splits services only when measured
  scale or deployment needs justify it.

## Stack

| Area | Choice |
| --- | --- |
| Web application | React, TypeScript, Vite; PixiJS and TanStack Query when needed |
| API | Python 3.12, FastAPI, Pydantic |
| Persistence | SQLAlchemy, Alembic, SQLite locally, PostgreSQL when shared |
| Analytics | Polars, NumPy, SciPy, DuckDB, PyArrow/Parquet |
| Media/CV | FFmpeg/ffprobe, OpenCV |
| Testing | pytest, Hypothesis, Vitest, React Testing Library, Playwright |
| Tooling | uv, pnpm, Ruff, mypy/pyright |
| Object storage | Local filesystem, with an S3-compatible adapter for deployment |

## Workspace

```text
apps/backend/          packaged FastAPI application and API tests
apps/web/              React application, generated API types, and component tests
packages/data-contracts/ versioned tracking/event schemas and examples
packages/sample-inputs/ source descriptors without redistributed media
docs/                  architecture, ADRs, data formats, and method notes
scripts/               contract, OpenAPI, and local sample orchestration
data/                  ignored local source and generated media
tests/contracts/       executable tracking and sample-builder contracts
```

The worker, persistence adapters, infrastructure definitions, and end-to-end media
tests shown in the architecture blueprint have not been introduced yet.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/) for Python environments and locking
- Python 3.12
- Node.js 24 LTS and Corepack 0.34.7 or newer
- pnpm 12.4.2, selected automatically from `packageManager` through Corepack
- FFmpeg, including `ffprobe`
- GNU Make
- A modern browser

The repository targets the Python 3.12 minor line for reproducible scientific and
computer-vision dependency support.

Node 24 installations with an older bundled Corepack can update it without
installing pnpm globally:

```bash
npm install --global corepack@0.34.7
corepack enable
```

## Local setup

Bootstrap the locked Python and JavaScript workspaces. The command creates `.env`
from `.env.example` only when `.env` does not already exist.

```bash
git clone <repository-url> tribuna
cd tribuna
make bootstrap
make dev
```

Development URLs:

- web health shell: `http://localhost:5173`
- API health: `http://localhost:8000/api/v1/health`
- FastAPI documentation: `http://localhost:8000/docs`
- OpenAPI document: `http://localhost:8000/openapi.json`

Run the complete CI-equivalent check locally:

```bash
make check
```

Useful focused commands are `make dev-api`, `make dev-web`, `make test`,
`make lint`, `make typecheck`, and `make generate`. Generated OpenAPI JSON and
TypeScript types are committed; `make check` fails if either drifts.

## Configuration

The backend reads these validated settings from `.env` or the process environment:

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRIBUNA_ENV` | `development` | `development`, `test`, or `production` |
| `TRIBUNA_DATABASE_URL` | `sqlite:///./data/tribuna.db` | Validated future persistence URL; no connection is opened yet |
| `TRIBUNA_OBJECT_STORE` | `filesystem` | `filesystem` or `s3`; not exercised yet |
| `TRIBUNA_OBJECT_ROOT` | `./data` | Future local object root |
| `TRIBUNA_WEB_ORIGIN` | `http://localhost:5173` | Exact direct-access CORS origin |
| `TRIBUNA_LOG_LEVEL` | `INFO` | Structured API logging level |

The Vite development server proxies `/api` to `127.0.0.1:8000`; the browser does
not need a hard-coded API server URL.

## Tracking data contract

Canonical tracking contract v1 is defined in
[`packages/data-contracts/tracking/v1`](packages/data-contracts/tracking/v1). The
directory contains its machine-readable schema, CSV rules, example CSV, and the
equivalent typed Parquet file.

Rebuild the binary example after an intentional contract/example change:

```bash
uv run python -m scripts.build_contract_examples
```

## Local sample video

Tribuna's video-only sample source is the tactical-camera upload identified by
YouTube video ID [`oXn0KPPHzuY`](https://www.youtube.com/watch?v=oXn0KPPHzuY).
Its observed metadata and usage notice are recorded in
[`packages/sample-inputs/youtube_oXn0KPPHzuY/source.json`](packages/sample-inputs/youtube_oXn0KPPHzuY/source.json).

No copy of the video or its frames is included in version control. The Tribuna
application and CI never download it automatically. For private, authorized use, a
developer can explicitly acquire a complete 1080p H.264/M4A source with the
project's `yt-dlp` development tool:

```bash
mkdir -p data/source
uv run yt-dlp \
  --no-playlist \
  --continue \
  --no-overwrites \
  --js-runtimes node \
  -f "bv[height<=1080][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080][ext=mp4]" \
  --merge-output-format mp4 \
  -o "data/source/youtube_oXn0KPPHzuY.%(ext)s" \
  "https://www.youtube.com/watch?v=oXn0KPPHzuY"
```

This command is user-initiated and is not run by setup scripts or CI. It must only
be used when authorized by the service, the relevant rights holders, or applicable
law.

Build the normalized 40-second sample beginning at source time `02:40` with:

```bash
uv run python -m scripts.build_youtube_sample \
  --video data/source/youtube_oXn0KPPHzuY.mp4 \
  --output data/fixtures/youtube_oXn0KPPHzuY
```

The generated, Git-ignored directory contains `sample.mp4` and `manifest.json`.
The sample maps source presentation timestamps `[160000000, 200000000)` to local
media timestamps `[0, 40000000)`, normalized to H.264/YUV420p at 25 fps while
preserving the source's coded width and height. For the documented source, the
result is 1920×1080. It contains exactly 1,000 frames, has no audio, and resets
output timestamps to zero. The manifest records input provenance, checksums, both
half-open intervals, and their one-to-one timeline mapping.

This video-only sample has no tracking observations, match clock, player identities,
or pitch calibration. The synthetic tracking examples above validate the independent
tracking contract. Supplying a local file does not imply permission to copy or use
it; developers are responsible for complying with the service terms, rights-holder
permissions, and applicable law.

## First demonstration workflow

The first end-to-end slice will be:

1. Create a match.
2. Upload a short tactical-camera MP4.
3. Import canonical tracking CSV data and inspect validation results.
4. Map video time to match time and calibrate the camera to the pitch.
5. Play and seek with synchronized player/ball overlays.
6. Open the pitch radar, Voronoi, and heatmap panels when their capabilities exist.

## Data conventions

- Canonical time is integer microseconds on a match timeline.
- Media synchronization uses presentation timestamps and piecewise timeline segments.
- Pitch coordinates are metres on the actual configured pitch dimensions.
- Image coordinates are pixels from the image's top-left corner.
- Raw, smoothed, and interpolated observations are distinct versioned datasets.
- Dense tracking observations live in Parquet; relational storage holds metadata,
  events, annotations, and job/analysis records.

See [docs/architecture.md](docs/architecture.md) for the full contracts and schema.

## Delivery plan

Work proceeds in small vertical slices:

1. Decisions, canonical fixture, and executable coordinate/time expectations
   (Milestone 0).
2. Repository foundation and CI (implemented).
3. Match creation and video playback.
4. Tracking import and validation.
5. Synchronized overlays.
6. Camera calibration and pitch radar.
7. Voronoi and heatmaps.
8. Durable/reproducible analysis jobs.
9. Analyst annotations, events, and exports.
10. PostgreSQL/S3 deployment hardening.

Each milestone and its acceptance tests are detailed in the architecture blueprint.

## Contributing

Until contributor guidelines are added:

- make changes as a tested vertical slice;
- add a regression fixture for every time/coordinate bug;
- keep provider-specific fields behind importer boundaries;
- document visualization methodology and units;
- record consequential architecture changes in `docs/adr/`.

## Licence

No licence has been selected yet. Add one before distributing the software. Video,
tracking, and event datasets may have separate licences and privacy restrictions;
record those with every source asset.
