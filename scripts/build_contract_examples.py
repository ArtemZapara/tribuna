"""Build typed binary examples for the tracking contract."""

from scripts.tracking_contract import (
    CONTRACT_DIR,
    load_contract,
    read_csv,
    validate_table,
    write_parquet,
)


def main() -> None:
    contract = load_contract()
    table = read_csv(CONTRACT_DIR / "example.csv", contract)
    validate_table(table, contract, pitch_length_m=105.0, pitch_width_m=68.0)
    write_parquet(CONTRACT_DIR / "example.parquet", table)


if __name__ == "__main__":
    main()
