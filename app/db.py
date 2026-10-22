import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings

logger = logging.getLogger(__name__)


def get_client(settings: Settings) -> AsyncIOMotorClient:
    # Cosmos DB for MongoDB (Azure) needs retrywrites=false in the URI; see README.
    return AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.services.create_index("url", unique=True)
    await db.checks.create_index([("service_id", 1), ("checked_at", -1)])
    await db.incidents.create_index([("service_id", 1), ("status", 1)])
    await db.incidents.create_index([("started_at", -1)])
    logger.info("MongoDB indexes ensured")


def serialize(doc: dict) -> dict:
    """Convert a Mongo document into a JSON-friendly dict (ObjectId -> str)."""
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    if "service_id" in out:
        out["service_id"] = str(out["service_id"])
    return out
