"""ASGI entry point for the Tribuna API process."""

from tribuna.adapters.api.app import create_app

app = create_app()
