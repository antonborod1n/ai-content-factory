from fastapi import APIRouter

from app.api.routes import (
    articles,
    competitor_topics,
    discovery,
    documents,
    health,
    projects,
    research,
    runs,
    settings,
    topics,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router, prefix="/api/v1")
api_router.include_router(topics.router, prefix="/api/v1")
api_router.include_router(settings.router, prefix="/api/v1")
api_router.include_router(articles.router, prefix="/api/v1")
api_router.include_router(documents.router, prefix="/api/v1")
api_router.include_router(research.router, prefix="/api/v1")
api_router.include_router(runs.router, prefix="/api/v1")
api_router.include_router(discovery.router, prefix="/api/v1")
api_router.include_router(competitor_topics.router, prefix="/api/v1")
