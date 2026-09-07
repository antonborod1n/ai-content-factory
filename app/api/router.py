from fastapi import APIRouter

from app.api.routes import articles, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(articles.router, prefix="/api/v1")
