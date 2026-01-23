
import os

import pytest
from httpx import AsyncClient

# Minimal env defaults so importing the app does not fail.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "testsecretkeytestsecretkeytestsecretkey")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from src.main import app

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
async def async_client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark as end-to-end test.")
    from src.config import settings
    settings.celery_task_always_eager = True
