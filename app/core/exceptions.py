"""Application-specific exceptions."""

import uuid


class AppError(Exception):
    """Base application error with a safe, user-facing message."""

    def __init__(self, message: str = "An application error occurred") -> None:
        self.message = message
        super().__init__(message)


class ArticleGenerationError(AppError):
    """Article generation failed inside the application."""

    def __init__(
        self,
        message: str = "Article generation failed",
        *,
        article_id: uuid.UUID | None = None,
    ) -> None:
        self.article_id = article_id
        super().__init__(message)


class ArticleGenerationUpstreamError(ArticleGenerationError):
    """Article generation failed because of the AI provider or its response."""


class AIError(AppError):
    """Base error for the AI layer (never includes secrets)."""

    def __init__(self, message: str = "AI generation failed") -> None:
        super().__init__(message)


class AIConfigurationError(AIError):
    """Missing or invalid AI configuration."""

    def __init__(self, message: str = "AI provider is not configured") -> None:
        super().__init__(message)


class AIProviderError(AIError):
    """Upstream AI provider failure (sanitized)."""

    def __init__(
        self, message: str = "Article generation failed due to an AI provider error"
    ) -> None:
        super().__init__(message)


class AIValidationError(AIError):
    """AI response could not be parsed or failed schema validation."""

    def __init__(
        self, message: str = "AI response failed validation"
    ) -> None:
        super().__init__(message)
