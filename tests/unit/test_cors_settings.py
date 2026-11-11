from app.config import Settings


def test_cors_origin_list_splits_and_strips() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://acf:x@localhost:5432/acf",
            "app_cors_origins": " http://localhost:5173 , http://127.0.0.1:5173 ",
        }
    )
    assert settings.cors_origin_list() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_empty_cors_origins_disables_list() -> None:
    settings = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://acf:x@localhost:5432/acf",
            "app_cors_origins": "  ",
        }
    )
    assert settings.cors_origin_list() == []
