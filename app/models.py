from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, examples=["GitHub API"])
    url: HttpUrl = Field(..., examples=["https://api.github.com"])
    expected_status: int = Field(200, ge=100, le=599)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("name must be at least 2 non-space characters")
        return v


class ServiceOut(BaseModel):
    id: str
    name: str
    url: str
    expected_status: int
    created_at: datetime
    last_checked_at: Optional[datetime] = None
    last_status: Optional[str] = None  # "up" | "down"


class IncidentOut(BaseModel):
    id: str
    service_id: str
    service_name: str
    status: str  # "open" | "resolved"
    started_at: datetime
    resolved_at: Optional[datetime] = None
    failure_count: int
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    last_response_time_ms: Optional[float] = None
