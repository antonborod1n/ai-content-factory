from fastapi import APIRouter, Response, status

from app.db.session import check_database_connection
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"description": "Application and database are healthy"},
        503: {"description": "Database is unavailable"},
    },
)
async def health(response: Response) -> HealthResponse:
    database_ok = await check_database_connection()
    if database_ok:
        return HealthResponse(status="ok", database="ok")

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="degraded", database="error")
