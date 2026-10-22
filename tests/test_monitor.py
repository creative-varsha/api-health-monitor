from datetime import datetime, timezone

import httpx

from app.checker import check_service
from app.poller import record_result
from tests.conftest import make_client

SERVICE = {
    "_id": "svc-1",
    "name": "Demo",
    "url": "https://demo.example.com/health",
    "expected_status": 200,
}


# 1 ---------------------------------------------------------------------------
async def test_check_success_records_status_and_latency():
    client = make_client(lambda req: httpx.Response(200, json={"ok": True}))
    result = await check_service(client, SERVICE)
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["response_time_ms"] is not None
    assert result["error"] is None


# 2 ---------------------------------------------------------------------------
async def test_check_5xx_is_failure_with_details():
    client = make_client(lambda req: httpx.Response(503))
    result = await check_service(client, SERVICE)
    assert result["success"] is False
    assert result["status_code"] == 503
    assert "Unexpected status 503" in result["error"]


# 3 ---------------------------------------------------------------------------
async def test_check_timeout_is_captured_not_raised():
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    result = await check_service(make_client(handler), SERVICE, timeout=1.0)
    assert result["success"] is False
    assert result["status_code"] is None
    assert "Timeout" in result["error"]


# 4 ---------------------------------------------------------------------------
async def test_repeated_failures_reuse_single_open_incident(db):
    await db.services.insert_one(dict(SERVICE))
    failure = {
        "service_id": "svc-1",
        "checked_at": datetime.now(timezone.utc),
        "status_code": 500,
        "response_time_ms": 12.0,
        "success": False,
        "error": "Unexpected status 500 (expected 200)",
    }
    await record_result(db, SERVICE, dict(failure))
    await record_result(db, SERVICE, dict(failure))
    await record_result(db, SERVICE, dict(failure))

    incidents = await db.incidents.find({}).to_list(length=10)
    assert len(incidents) == 1
    assert incidents[0]["status"] == "open"
    assert incidents[0]["failure_count"] == 3


# 5 ---------------------------------------------------------------------------
async def test_incident_resolves_when_service_recovers(db):
    await db.services.insert_one(dict(SERVICE))
    now = datetime.now(timezone.utc)
    bad = {"service_id": "svc-1", "checked_at": now, "status_code": 500,
           "response_time_ms": 5.0, "success": False, "error": "boom"}
    good = {"service_id": "svc-1", "checked_at": now, "status_code": 200,
            "response_time_ms": 5.0, "success": True, "error": None}

    await record_result(db, SERVICE, dict(bad))
    await record_result(db, SERVICE, dict(good))

    incident = await db.incidents.find_one({})
    assert incident["status"] == "resolved"
    assert incident["resolved_at"] is not None


# 6 ---------------------------------------------------------------------------
async def test_register_validation_and_duplicate_rejected(api):
    bad_url = await api.post("/services", json={"name": "Bad", "url": "not-a-url"})
    assert bad_url.status_code == 422

    payload = {"name": "GitHub", "url": "https://api.github.com"}
    first = await api.post("/services", json=payload)
    assert first.status_code == 201
    assert first.json()["name"] == "GitHub"

    dup = await api.post("/services", json=payload)
    assert dup.status_code == 409
