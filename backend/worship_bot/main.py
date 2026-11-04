import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from worship_bot.api.request_logging import RequestLoggingMiddleware
from worship_bot.api.routers import router
from worship_bot.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging("api")
    logger = logging.getLogger(__name__)
    logger.info("service.started")
    try:
        yield
    finally:
        logger.info("service.stopped")


app = FastAPI(title="Worship Team Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}
