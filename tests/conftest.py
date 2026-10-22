import httpx
import pytest
from httpx import ASGITransport
from mongomock_motor import AsyncMongoMockClient

from app.main import app


@pytest.fixture
async def db():
    client = AsyncMongoMockClient()
    database = client["test_monitor"]
    await database.services.create_index("url", unique=True)
    return database


@pytest.fixture
async def api(db):
    """HTTP client wired straight to the FastAPI app with the mock DB (no poller)."""
    app.state.db = db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_client(handler) -> httpx.AsyncClient:
    """An httpx client whose 'network' is a local handler function."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
