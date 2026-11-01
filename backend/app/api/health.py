from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.redis import get_redis
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)) -> dict:
    checks = {"db": "ok", "redis": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["db"] = "error"
    try:
        get_redis().ping()
    except Exception:
        checks["redis"] = "error"
    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", **checks}
