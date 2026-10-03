"""Entry point for running the API: `uv run fastapi dev src/expense_splitter/main.py`."""

import os

from expense_splitter.app import create_app

app = create_app(os.environ.get("EXPENSE_SPLITTER_DB", "expense_splitter.db"))
