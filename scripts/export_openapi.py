"""Export Tribuna's OpenAPI contract deterministically."""

from __future__ import annotations

import argparse
import json

from pathlib import Path

from tribuna.adapters.api.app import create_app
from tribuna.config import Settings

DEFAULT_OUTPUT = Path("apps/web/openapi.json")


def render_openapi() -> str:
    """Return the canonical OpenAPI document."""
    settings = Settings(environment="development", _env_file=None)
    document = create_app(settings).openapi()
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_openapi()

    if args.check:
        if not args.output.is_file() or args.output.read_text() != rendered:
            raise SystemExit(
                f"generated OpenAPI contract is stale: run with --output {args.output}"
            )
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)


if __name__ == "__main__":
    main()
