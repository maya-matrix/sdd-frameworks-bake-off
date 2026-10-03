from fastapi import FastAPI

from splitit.api import router
from splitit.errors import register_error_handlers
from splitit.repository import InMemoryRepository


def create_app() -> FastAPI:
    app = FastAPI(title="SplitIt Expense Splitting API", version="1.0.0")
    app.state.repository = InMemoryRepository()
    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
