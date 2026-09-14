# ADR 0003: Use microsecond timelines and explicit media mappings

- Status: accepted
- Date: 2026-09-11

## Context

Football video may contain variable frame rates, clipped periods, stoppages, and
discontinuities. Provider frame numbers and nominal frame rates are insufficient as
a universal synchronization key.

## Decision

- Persist time as integer microseconds in fields ending with `_us`.
- Use half-open intervals `[start_us, end_us)`.
- Treat media presentation timestamps as authoritative for playback.
- Retain provider timestamps and frame numbers as provenance.
- Map media time to canonical match time with explicit, non-overlapping, piecewise
  linear timeline segments.
- Missing observations remain gaps. Interpolation is opt-in and declares a method and
  maximum gap.

## Consequences

Frontend views share one playback clock. Importers must not infer variable-rate media
time from `frame_number / nominal_fps`. Tests use interval-boundary and discontinuity
examples in addition to the normal slope-one mapping.

