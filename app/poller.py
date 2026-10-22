import asyncio
import logging
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.checker import check_service
from app.config import Settings
from app.logging_config import log_extra

logger = logging.getLogger(__name__)


async def record_result(db: AsyncIOMotorDatabase, service: dict, result: dict) -> None:
    """Persist a check and open / update / resolve the service's incident."""
    await db.checks.insert_one(dict(result))
    await db.services.update_one(
        {"_id": service["_id"]},
        {
            "$set": {
                "last_checked_at": result["checked_at"],
                "last_status": "up" if result["success"] else "down",
            }
        },
    )

    open_incident = await db.incidents.find_one(
        {"service_id": service["_id"], "status": "open"}
    )

    if not result["success"]:
        fields = {
            "last_status_code": result["status_code"],
            "last_error": result["error"],
            "last_response_time_ms": result["response_time_ms"],
        }
        if open_incident is None:
            await db.incidents.insert_one(
                {
                    "service_id": service["_id"],
                    "service_name": service["name"],
                    "status": "open",
                    "started_at": result["checked_at"],
                    "resolved_at": None,
                    "failure_count": 1,
                    **fields,
                }
            )
            logger.warning("incident opened", extra=log_extra(service=service["name"]))
        else:
            await db.incidents.update_one(
                {"_id": open_incident["_id"]},
                {"$inc": {"failure_count": 1}, "$set": fields},
            )
    elif open_incident is not None:
        await db.incidents.update_one(
            {"_id": open_incident["_id"]},
            {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc)}},
        )
        logger.info("incident resolved", extra=log_extra(service=service["name"]))


async def run_cycle(
    db: AsyncIOMotorDatabase, client: httpx.AsyncClient, settings: Settings
) -> int:
    """Check every registered service concurrently. Returns number of services checked."""
    services = await db.services.find({}).to_list(length=1000)
    if not services:
        return 0

    results = await asyncio.gather(
        *(
            check_service(
                client,
                s,
                settings.request_timeout_seconds,
                settings.latency_threshold_ms,
            )
            for s in services
        ),
        return_exceptions=True,
    )
    for service, result in zip(services, results):
        if isinstance(result, Exception):
            logger.error(
                "check crashed",
                exc_info=result,
                extra=log_extra(service=service["name"]),
            )
            continue
        try:
            await record_result(db, service, result)
        except Exception:
            logger.exception("failed to persist result", extra=log_extra(service=service["name"]))
    return len(services)


async def poll_forever(db: AsyncIOMotorDatabase, settings: Settings) -> None:
    logger.info(
        "poller started", extra=log_extra(interval_seconds=settings.poll_interval_seconds)
    )
    async with httpx.AsyncClient(headers={"User-Agent": "api-health-monitor/1.0"}) as client:
        while True:
            try:
                count = await run_cycle(db, client, settings)
                logger.info("poll cycle finished", extra=log_extra(services_checked=count))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("poll cycle failed")
            await asyncio.sleep(settings.poll_interval_seconds)
