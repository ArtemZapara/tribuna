# Tribuna

Tribuna is a demonstration and research workspace for football analysis. It pairs
tactical-camera video with synchronized overlays and optional analytical views such
as a top-down pitch radar, Voronoi regions, heatmaps, events, and derived metrics.

> **Status:** Milestone 0 data-contract phase. The current repository contains the
> executable tracking contract and reference fixtures; the application layout and
> runtime dependencies described below remain the target for later milestones.

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

## Proposed stack

| Area | Choice |
| --- | --- |
| Web application | React, TypeScript, Vite, PixiJS, TanStack Query |
| API | Python 3.12, FastAPI, Pydantic |
| Persistence | SQLAlchemy, Alembic, SQLite locally, PostgreSQL when shared |
| Analytics | Polars, NumPy, SciPy, DuckDB, PyArrow/Parquet |
| Media/CV | FFmpeg/ffprobe, OpenCV |
| Testing | pytest, Hypothesis, Vitest, React Testing Library, Playwright |
| Tooling | uv, pnpm, Ruff, mypy/pyright |
| Object storage | Local filesystem, with an S3-compatible adapter for deployment |

## Planned workspace

```text
apps/backend/          FastAPI application, domain, importers, and analytics
apps/worker/           long-running import, media, and analysis jobs
apps/web/              React analysis workspace
packages/data-contracts/ versioned tracking/event schemas and examples
packages/sample-inputs/ source descriptors without redistributed media
docs/                  architecture, ADRs, data formats, and method notes
infra/                 container and local deployment definitions
data/                  ignored local raw/canonical/derived assets
tests/e2e/             cross-application user journeys
```

## Prerequisites

For the target application:

- Git
- [uv](https://docs.astral.sh/uv/) for Python environments and locking
- Python 3.12
- Node.js current LTS and [pnpm](https://pnpm.io/)
- FFmpeg, including `ffprobe`
- A modern browser with WebGL support
- Docker/Compose only for the shared-infrastructure profile

The repository targets the Python 3.12 minor line for reproducible scientific and
computer-vision dependency support.

## Current scaffold setup

Until milestone 1 restructures the repository, the existing placeholder can be run
with:

```bash
git clone <repository-url> tribuna
cd tribuna
uv sync
uv run python main.py
```

Expected output:

```text
Hello from tribuna!
```

Run the checks currently available:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

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

Build the normalized ten-frame sample from the resulting local copy with:

```bash
uv run python -m scripts.build_youtube_sample \
  --video data/source/youtube_oXn0KPPHzuY.mp4 \
  --output data/fixtures/youtube_oXn0KPPHzuY
```

The generated, Git-ignored directory contains `sample.mp4` and `manifest.json`.
The sample is the first ten decoded frames normalized to H.264/YUV420p at 960×540
and 25 fps, without audio and with media timestamps starting at zero. The manifest
records input provenance, checksums, and the half-open media interval
`[0, 400000)` microseconds.

This video-only sample has no tracking observations, match clock, player identities,
or pitch calibration. The synthetic tracking examples above validate the independent
tracking contract. Supplying a local file does not imply permission to copy or use
it; developers are responsible for complying with the service terms, rights-holder
permissions, and applicable law.

## Target local setup

These commands are the intended developer experience after milestone 1; they are
documented now as an acceptance criterion and are not implemented yet.

```bash
git clone <repository-url> tribuna
cd tribuna
cp .env.example .env
make bootstrap
make dev
```

The development services will be:

- web UI: `http://localhost:5173`
- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`

Run all static and automated checks with:

```bash
make check
```

Run the API and web suites independently with:

```bash
uv run pytest
pnpm --dir apps/web test
pnpm --dir apps/web exec playwright test
```

## Planned configuration

`.env.example` will document at least:

```dotenv
TRIBUNA_ENV=development
TRIBUNA_DATABASE_URL=sqlite:///./data/tribuna.db
TRIBUNA_OBJECT_STORE=filesystem
TRIBUNA_OBJECT_ROOT=./data
TRIBUNA_WEB_ORIGIN=http://localhost:5173
TRIBUNA_LOG_LEVEL=INFO
```

Deployed environments will replace the database URL and object-store settings with
PostgreSQL and S3-compatible credentials. Secrets must never be committed.

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
2. Repository foundation and CI.
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
