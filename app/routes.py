import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import DuplicateKeyError

from app.db import serialize
from app.logging_config import log_extra
from app.models import IncidentOut, ServiceCreate, ServiceOut

logger = logging.getLogger(__name__)
router = APIRouter()


def get_db(request: Request):
    return request.app.state.db


@router.post("/services", response_model=ServiceOut, status_code=201, tags=["services"])
async def register_service(payload: ServiceCreate, db=Depends(get_db)):
    """Register a new service to be monitored every poll interval."""
    doc = {
        "name": payload.name,
        "url": str(payload.url),
        "expected_status": payload.expected_status,
        "created_at": datetime.now(timezone.utc),
        "last_checked_at": None,
        "last_status": None,
    }
    try:
        result = await db.services.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="A service with this URL is already registered")
    doc["_id"] = result.inserted_id
    logger.info("service registered", extra=log_extra(service=doc["name"], url=doc["url"]))
    return serialize(doc)


@router.get("/services", response_model=list[ServiceOut], tags=["services"])
async def list_services(db=Depends(get_db)):
    """List all monitored services with their latest known status."""
    docs = await db.services.find({}).sort("created_at", 1).to_list(length=1000)
    return [serialize(d) for d in docs]


@router.get("/incidents", response_model=list[IncidentOut], tags=["incidents"])
async def get_incidents(
    service_id: Optional[str] = Query(None, description="Filter by service id"),
    status: Optional[Literal["open", "resolved"]] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    """Incident history, newest first. Optionally filter by service and status."""
    query: dict = {}
    if service_id:
        try:
            query["service_id"] = ObjectId(service_id)
        except (InvalidId, TypeError):
            raise HTTPException(status_code=422, detail="service_id is not a valid id")
    if status:
        query["status"] = status
    docs = await db.incidents.find(query).sort("started_at", -1).to_list(length=limit)
    return [serialize(d) for d in docs]
