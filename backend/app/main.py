from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import REGISTRY

from app.api import (
    admin,
    applications,
    auth,
    companies,
    health,
    interviews,
    jobs,
    profile,
    recruiter,
    resumes,
    saved_searches,
    stats,
)
from app.core.config import settings
from app.core.health import DependencyCollector
from app.core.observability import (
    ConcurrencyLimitMiddleware,
    ObservabilityMiddleware,
    configure_logging,
    init_sentry,
)
from app.ml.classifier import get_classifier
from app.ml.embeddings import get_embedder
from app.tasks import definitions as _tasks  # noqa: F401  registers the Celery tasks

configure_logging()
init_sentry()
_collector = DependencyCollector()
REGISTRY.register(_collector)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model and classifier once per process, not on the first request.
    get_embedder()
    get_classifier()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hike API",
        version="1.1.0",
        description="Job portal and recruitment platform with resume parsing and AI matching.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    # Load shedding sits inside observability, so shed requests are still logged and counted.
    app.add_middleware(ConcurrencyLimitMiddleware)
    # Added last = outermost: request ids and timings cover CORS handling too.
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api")
    app.include_router(health.metrics_router)
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(recruiter.router)
    app.include_router(resumes.router)
    app.include_router(stats.router)
    app.include_router(applications.router)
    app.include_router(profile.router)
    app.include_router(profile.account_router)
    app.include_router(admin.router)
    app.include_router(interviews.router)
    app.include_router(saved_searches.router)
    app.include_router(companies.router)
    return app


app = create_app()
