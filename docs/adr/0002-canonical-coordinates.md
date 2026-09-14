# ADR 0002: Use metric, source-oriented pitch coordinates

- Status: accepted
- Date: 2026-09-11

## Context

Tracking providers use different units, origins, axes, and attacking-direction
normalizations. Image overlays additionally use pixel coordinates with a different
origin.

## Decision

- Canonical pitch coordinates use metres and the match's configured pitch length and
  width.
- The origin is the bottom-left of the physical pitch in source orientation. `x`
  follows pitch length and `y` follows pitch width.
- Provider coordinates are retained in immutable raw data. Direction-normalized
  coordinates are derived views and do not replace canonical values.
- Image coordinates use pixels with a top-left origin, positive right and down.
- Out-of-bounds positions remain unchanged and receive a quality flag.
- Calibration records define transform direction, validity interval, method, control
  points, and reprojection error.

## Consequences

Every importer must document and test its coordinate conversion. Every match must
carry pitch dimensions. Visualizations may clip geometry for display, but analytics
must operate on the retained coordinates unless their methodology says otherwise.

