"""Read, validate, and write Tribuna tracking-contract tables."""

from __future__ import annotations

import csv
import json
import math

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "packages" / "data-contracts" / "tracking" / "v1"
SCHEMA_PATH = CONTRACT_DIR / "schema.json"

ARROW_TYPES: dict[str, pa.DataType] = {
    "bool": pa.bool_(),
    "float32": pa.float32(),
    "int8": pa.int8(),
    "int64": pa.int64(),
    "string": pa.string(),
    "uint32": pa.uint32(),
}


class ContractError(ValueError):
    """Raised when tabular data violates the tracking contract."""


def load_contract(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    """Load the machine-readable tracking contract."""
    return json.loads(path.read_text(encoding="utf-8"))


def arrow_schema(contract: dict[str, Any]) -> pa.Schema:
    """Build the contract's Arrow schema, including required metadata."""
    properties = contract["properties"]
    fields = [
        pa.field(
            name,
            ARROW_TYPES[properties[name]["x-arrow-type"]],
            nullable=properties[name]["x-nullable"],
        )
        for name in contract["x-column-order"]
    ]
    metadata = {
        key.encode(): value.encode()
        for key, value in contract["x-parquet-schema-metadata"].items()
    }
    return pa.schema(fields, metadata=metadata)


def read_csv(path: Path, contract: dict[str, Any]) -> pa.Table:
    """Read a canonical CSV using the exact contract types."""
    schema = arrow_schema(contract)
    column_types = {field.name: field.type for field in schema}
    options = contract["x-csv"]
    table = pa_csv.read_csv(
        path,
        read_options=pa_csv.ReadOptions(encoding=options["encoding"]),
        parse_options=pa_csv.ParseOptions(delimiter=options["delimiter"]),
        convert_options=pa_csv.ConvertOptions(
            column_types=column_types,
            false_values=[options["false"]],
            null_values=[options["null"]],
            strings_can_be_null=True,
            true_values=[options["true"]],
        ),
    )
    return pa.Table.from_arrays(table.columns, schema=schema)


def write_csv(path: Path, rows: list[dict[str, Any]], contract: dict[str, Any]) -> None:
    """Write deterministic canonical CSV rows."""
    columns = contract["x-column-order"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in columns})


def write_parquet(path: Path, table: pa.Table) -> None:
    """Write a deterministic logical Parquet representation."""
    pq.write_table(table, path, compression="zstd", use_dictionary=True)


def validate_table(
    table: pa.Table,
    contract: dict[str, Any],
    *,
    pitch_length_m: float | None = None,
    pitch_width_m: float | None = None,
) -> None:
    """Validate schema, values, ordering, and optional pitch-bound flags."""
    expected_schema = arrow_schema(contract)
    if table.schema != expected_schema:
        raise ContractError(
            f"schema mismatch:\nexpected {expected_schema}\nactual {table.schema}"
        )

    properties = contract["properties"]
    rows = table.to_pylist()
    for index, row in enumerate(rows):
        _validate_row(index, row, properties)
        if pitch_length_m is not None and pitch_width_m is not None:
            outside = not (
                0.0 <= row["x_m"] <= pitch_length_m
                and 0.0 <= row["y_m"] <= pitch_width_m
            )
            flagged = bool(row["quality_flags"] & 1)
            if outside != flagged:
                raise ContractError(
                    f"row {index}: out-of-bounds flag is {flagged}, expected {outside}"
                )

    sort_keys = [_sort_key(row) for row in rows]
    if sort_keys != sorted(sort_keys):
        raise ContractError("rows are not in canonical order")


def _validate_row(
    index: int,
    row: dict[str, Any],
    properties: dict[str, dict[str, Any]],
) -> None:
    for name, rules in properties.items():
        value = row[name]
        if value is None:
            if not rules["x-nullable"]:
                raise ContractError(f"row {index}: {name} must not be null")
            continue
        if rules.get("x-finite") and not math.isfinite(value):
            raise ContractError(f"row {index}: {name} must be finite")
        if "const" in rules and value != rules["const"]:
            raise ContractError(f"row {index}: {name} must equal {rules['const']!r}")
        allowed = rules.get("enum")
        if allowed is not None and value not in allowed:
            raise ContractError(f"row {index}: unsupported {name} {value!r}")
        if isinstance(value, str) and len(value) < rules.get("minLength", 0):
            raise ContractError(f"row {index}: {name} must not be empty")
        if "minimum" in rules and value < rules["minimum"]:
            raise ContractError(f"row {index}: {name} is below its minimum")
        if "maximum" in rules and value > rules["maximum"]:
            raise ContractError(f"row {index}: {name} is above its maximum")


def _sort_key(row: dict[str, Any]) -> tuple[int, int, str, tuple[bool, str]]:
    entity_id = row["entity_id"]
    return (
        row["period"],
        row["match_time_us"],
        row["entity_type"],
        (entity_id is None, entity_id or ""),
    )


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value
