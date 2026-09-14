# Tribuna tracking contract v1

This directory is the source of truth for canonical dense tracking observations in
Tribuna. Version `1.0` represents one entity observation at one match time. The same
logical rows may be encoded as CSV for interchange or Parquet for application
storage.

## Files

- `schema.json`: machine-readable row schema, column order, enums, Arrow types, and
  CSV encoding rules.
- `example.csv`: synthetic human-readable example covering a player, official, and
  ball.
- `example.parquet`: typed Parquet equivalent of `example.csv`.

## Semantics

- One row is one observation, not a complete frame.
- `match_time_us` is the canonical match timeline in integer microseconds.
- `source_time_us` and `frame_number` retain source provenance and may be null.
- Pitch position is stored in metres using Tribuna's bottom-left, source-oriented
  coordinate system.
- Image position is the entity's pitch-contact point in pixels using a top-left
  origin. For a person bounding box this is normally its bottom centre.
- `entity_type` describes the broad entity class. `role` is a more specific,
  potentially time-varying function such as goalkeeper or referee.
- `visible` describes whether the entity is visible in the associated image;
  `in_play` describes sporting state. They are independent and nullable.
- Null means unavailable or inapplicable. It is not equivalent to zero, false, or an
  empty identifier.

Rows are sorted by `period`, `match_time_us`, `entity_type`, and `entity_id`, with
null entity IDs ordered last.

## CSV encoding

- UTF-8 without a byte-order mark.
- A header is required and uses the exact order in `schema.json`.
- The delimiter is a comma and the record terminator is LF.
- Empty fields encode null values; quoted empty strings are not valid identifiers.
- Boolean values are lowercase `true` and `false`.
- Floating-point values use decimal notation. `NaN`, positive infinity, and negative
  infinity are invalid.
- Unknown columns are rejected for contract v1.

## Parquet encoding

Parquet columns use the exact Arrow types and nullability declared in `schema.json`.
Dictionary encoding and compression are physical writer choices and do not change
the contract. Writers must attach these schema metadata values:

```text
tribuna.contract=tracking
tribuna.schema_version=1.0
```

## Quality flags

`quality_flags` is an unsigned 32-bit bit mask:

| Bit | Value | Meaning |
| --- | ---: | --- |
| 0 | `1` | Pitch coordinate is outside configured pitch bounds |
| 1 | `2` | Identity is unresolved |
| 2 | `4` | Observation was interpolated |
| 3 | `8` | Observation has low source confidence |
| 4–31 |  | Reserved; writers must emit zero until assigned |

Flags may be combined. An out-of-bounds observation remains unchanged.

## Compatibility

Adding an optional nullable field is backward-compatible within v1 after updating
the minor schema version and contract tests. Removing or renaming a field, changing
its type, unit, nullability, enum meaning, coordinate system, or time semantics
requires a new major contract directory such as `v2/`.
