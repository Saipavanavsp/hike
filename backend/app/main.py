import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, jobs, recruiter, resumes, stats
from app.core.config import settings
from app.ml.classifier import get_classifier
from app.ml.embeddings import get_embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedding model and classifier once per process, not on the first request.
    get_embedder()
    get_classifier()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hike API",
        version="1.0.0",
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
    )
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(recruiter.router)
    app.include_router(resumes.router)
    app.include_router(stats.router)
    return app


app = create_app()
