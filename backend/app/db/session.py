from collections.abc import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_size + max_overflow must cover settings.max_concurrent_requests, which caps how many
# requests run at once (see ConcurrencyLimitMiddleware). pool_timeout is short so a request
# that cannot get a connection fails fast instead of holding a worker thread.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[Session]:
    """Request-scoped session.

    Deliberately an *async* generator around a sync Session. FastAPI runs the cleanup of a
    sync generator dependency in the thread pool; when every thread is busy waiting for a
    database connection, the requests that hold connections cannot run their cleanup to give
    them back, and the process deadlocks (found by the 500-user load test). An async
    generator closes the session on the event loop, so connections are always returned.
    The session itself is lazy: creating it takes no connection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
