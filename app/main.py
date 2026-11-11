import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, init_engine
from app.services.recovery_service import recover_interrupted_work

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log_level = configure_logging(settings)
    logger.info(
        "Application started env=%s log_level=%s",
        settings.app_env,
        log_level,
    )
    init_engine()
    try:
        await recover_interrupted_work()
    except Exception:
        logger.exception("Could not close interrupted work")
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(
        title="AI Content Factory",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    register_exception_handlers(application)
    origins = get_settings().cors_origin_list()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    return application


app = create_app()
