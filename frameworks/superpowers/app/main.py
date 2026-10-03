"""Application factory. Run with: uv run uvicorn app.main:create_app --factory"""

import os

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import register_error_handlers, router
from app.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./expenses.db"


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    app = FastAPI(title="Expense Splitter")
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.include_router(router)
    register_error_handlers(app)
    return app
