import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import get_client, init_indexes
from app.logging_config import setup_logging
from app.poller import poll_forever
from app.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)

    client = get_client(settings)
    db = client[settings.mongodb_db]
    app.state.db = db
    await init_indexes(db)

    poller_task = None
    if settings.enable_poller:
        poller_task = asyncio.create_task(poll_forever(db, settings))

    yield

    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
    client.close()
    logger.info("shutdown complete")


app = FastAPI(
    title="API Health & Incident Monitor",
    description="Polls registered endpoints every 5 minutes and tracks incidents in MongoDB.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe used by Azure App Service / Container Apps."""
    return {"status": "ok"}
