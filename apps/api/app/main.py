from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.db import close_db_pool, init_db_pool
from app.core.logging import configure_logging
from app.core.middleware import correlation_and_rate_limit_middleware

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db_pool()
    try:
        yield
    finally:
        await close_db_pool()


app = FastAPI(title="DocsAI API", version="0.1.0", lifespan=lifespan)
app.middleware("http")(correlation_and_rate_limit_middleware)
app.include_router(router)
