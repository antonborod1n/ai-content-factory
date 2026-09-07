"""Application-specific exceptions."""


class AppError(Exception):
    """Base application error with a safe, user-facing message."""

    def __init__(self, message: str = "An application error occurred") -> None:
        self.message = message
        super().__init__(message)


class ArticleGenerationError(AppError):
    """Article generation failed for a reason that is not AI-specific."""

    def __init__(self, message: str = "Article generation failed") -> None:
        super().__init__(message)


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
