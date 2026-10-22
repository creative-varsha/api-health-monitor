import logging
import time
from datetime import datetime, timezone

import httpx

from app.logging_config import log_extra

logger = logging.getLogger(__name__)


async def check_service(
    client: httpx.AsyncClient,
    service: dict,
    timeout: float = 10.0,
    latency_threshold_ms: float = 2000.0,
) -> dict:
    """Hit a service once and return a check-result document.

    A check fails when the request errors out (timeout / connection problem),
    the status code differs from the expected one, or latency exceeds the threshold.
    """
    started = time.perf_counter()
    result = {
        "service_id": service["_id"],
        "checked_at": datetime.now(timezone.utc),
        "status_code": None,
        "response_time_ms": None,
        "success": False,
        "error": None,
    }
    try:
        response = await client.get(service["url"], timeout=timeout, follow_redirects=True)
        elapsed_ms = (time.perf_counter() - started) * 1000
        result["status_code"] = response.status_code
        result["response_time_ms"] = round(elapsed_ms, 2)

        expected = service.get("expected_status", 200)
        if response.status_code != expected:
            result["error"] = f"Unexpected status {response.status_code} (expected {expected})"
        elif elapsed_ms > latency_threshold_ms:
            result["error"] = f"Slow response: {elapsed_ms:.0f}ms > {latency_threshold_ms:.0f}ms"
        else:
            result["success"] = True
    except httpx.TimeoutException:
        result["response_time_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["error"] = f"Timeout after {timeout}s"
    except httpx.HTTPError as exc:
        result["response_time_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["error"] = f"{type(exc).__name__}: {exc}"

    logger.info(
        "check complete",
        extra=log_extra(
            service=service["name"],
            success=result["success"],
            status_code=result["status_code"],
            response_time_ms=result["response_time_ms"],
            error=result["error"],
        ),
    )
    return result
