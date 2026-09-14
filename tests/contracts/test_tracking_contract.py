from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from scripts.tracking_contract import (
    ARROW_TYPES,
    CONTRACT_DIR,
    ContractError,
    arrow_schema,
    load_contract,
    read_csv,
    validate_table,
)

EXPECTED_COLUMNS = (
    "schema_version",
    "match_id",
    "dataset_id",
    "period",
    "match_time_us",
    "source_time_us",
    "frame_number",
    "entity_type",
    "role",
    "entity_id",
    "team_id",
    "x_m",
    "y_m",
    "z_m",
    "vx_mps",
    "vy_mps",
    "speed_mps",
    "image_x_px",
    "image_y_px",
    "visible",
    "in_play",
    "confidence",
    "quality_flags",
)


def test_machine_readable_contract_defines_order_types_and_nullability() -> None:
    contract = load_contract()
    schema = arrow_schema(contract)

    assert contract["x-contract"] == "tracking"
    assert contract["x-schema-version"] == "1.0"
    assert tuple(contract["x-column-order"]) == EXPECTED_COLUMNS
    assert tuple(schema.names) == EXPECTED_COLUMNS

    for field in schema:
        definition = contract["properties"][field.name]
        assert field.type == ARROW_TYPES[definition["x-arrow-type"]]
        assert field.nullable is definition["x-nullable"]

    assert contract["properties"]["entity_type"]["enum"] == [
        "player",
        "ball",
        "official",
        "unknown",
    ]
    assert contract["properties"]["role"]["enum"] == [
        "outfield_player",
        "goalkeeper",
        "referee",
        "assistant_referee",
        "other",
        None,
    ]


def test_csv_and_parquet_examples_are_logically_identical() -> None:
    contract = load_contract()
    csv_table = read_csv(CONTRACT_DIR / "example.csv", contract)
    parquet_table = pq.read_table(CONTRACT_DIR / "example.parquet")

    validate_table(
        csv_table,
        contract,
        pitch_length_m=105.0,
        pitch_width_m=68.0,
    )
    validate_table(
        parquet_table,
        contract,
        pitch_length_m=105.0,
        pitch_width_m=68.0,
    )
    assert csv_table.equals(parquet_table)
    assert parquet_table.schema.metadata == {
        b"tribuna.contract": b"tracking",
        b"tribuna.schema_version": b"1.0",
    }


def test_out_of_bounds_observation_is_retained_and_flagged() -> None:
    contract = load_contract()
    table = read_csv(CONTRACT_DIR / "example.csv", contract)
    outside = [row for row in table.to_pylist() if row["quality_flags"] & 1]

    assert len(outside) == 1
    assert outside[0]["x_m"] == pytest.approx(106.0)


def test_validator_rejects_non_finite_coordinates() -> None:
    contract = load_contract()
    table = read_csv(CONTRACT_DIR / "example.csv", contract)
    x_column = table["x_m"].to_pylist()
    x_column[0] = float("nan")
    invalid = table.set_column(
        table.schema.get_field_index("x_m"),
        table.schema.field("x_m"),
        pa.array(x_column, type=pa.float32()),
    )

    with pytest.raises(ContractError, match="x_m must be finite"):
        validate_table(invalid, contract)
