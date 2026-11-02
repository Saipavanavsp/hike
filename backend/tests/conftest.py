import os
import tempfile

# Point the app at the test database / redis db BEFORE anything imports app.core.config.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://hike:hike@localhost:5432/hike_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="hike-test-storage-")
os.environ["APP_ENV"] = "test"
os.environ["COOKIE_SECURE"] = "false"
# Background tasks run inline; the sandboxed parser has its own tests (test_security.py).
os.environ["TASKS_EAGER"] = "true"
os.environ["PARSER_ISOLATION"] = "inline"
os.environ["MALWARE_SCAN"] = "heuristic"
os.environ["LOG_FORMAT"] = "text"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.redis import get_redis  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    """Recreate the schema from Alembic migrations once per test session."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_state():
    yield
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    if tables:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    get_redis().flushdb()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from app.main import app

    # The app sends the CSRF header on every request, like the frontend does.
    with TestClient(app, headers={"X-CSRF-Protection": "1"}) as c:
        yield c
