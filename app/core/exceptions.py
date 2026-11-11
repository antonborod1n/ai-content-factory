"""Application-specific exceptions."""

import uuid

# Shown when a job dies with the process or its task is cancelled.
# Safe for the operator UI: no secrets, no article text.
INTERRUPTED_MESSAGE = "Генерация прервана: сервер остановился до завершения"


class AppError(Exception):
    """Base application error with a safe, user-facing message."""

    def __init__(self, message: str = "An application error occurred") -> None:
        self.message = message
        super().__init__(message)


class ProjectProtectedError(AppError):
    """The default project must stay."""


class ProjectNotFoundError(AppError):
    """No project with this id."""


class RunNotFoundError(AppError):
    """No task run with this id in the current project."""

    def __init__(self, run_id: uuid.UUID) -> None:
        self.run_id = run_id
        super().__init__("Run not found")


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


class ArticleNotFoundError(ArticleGenerationError):
    """Requested article does not exist."""

    def __init__(self, article_id: uuid.UUID) -> None:
        super().__init__("Article not found", article_id=article_id)


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


class DocumentError(AppError):
    """Knowledge-base document operation failed inside the application."""

    def __init__(
        self,
        message: str = "Document operation failed",
        *,
        document_id: uuid.UUID | None = None,
    ) -> None:
        self.document_id = document_id
        super().__init__(message)


class DocumentNotFoundError(DocumentError):
    """Requested document does not exist."""

    def __init__(self, document_id: uuid.UUID) -> None:
        super().__init__("Document not found", document_id=document_id)


class DocumentParseError(DocumentError):
    """Uploaded or pasted content could not be turned into text."""

    def __init__(self, message: str = "Document could not be parsed") -> None:
        super().__init__(message)


class DocumentIngestError(DocumentError):
    """Ingest failed after the document row was created."""


class DocumentIngestUpstreamError(DocumentIngestError):
    """Ingest failed because of the embedding provider."""


class ResearchError(AppError):
    """Competitor research failed inside the application."""

    def __init__(
        self,
        message: str = "Competitor research failed",
        *,
        research_id: uuid.UUID | None = None,
    ) -> None:
        self.research_id = research_id
        super().__init__(message)


class ResearchNotFoundError(ResearchError):
    """Requested research run does not exist."""

    def __init__(self, research_id: uuid.UUID) -> None:
        super().__init__("Research not found", research_id=research_id)


class ResearchConfigurationError(ResearchError):
    """Missing search key or research is disabled."""

    def __init__(
        self, message: str = "Competitor research is not configured"
    ) -> None:
        super().__init__(message)


class ResearchUpstreamError(ResearchError):
    """SERP provider or page-fetch cluster failed."""


class DiscoveryError(AppError):
    """Topic discovery failed inside the application."""

    def __init__(
        self,
        message: str = "Topic discovery failed",
        *,
        plan_id: uuid.UUID | None = None,
    ) -> None:
        self.plan_id = plan_id
        super().__init__(message)


class DiscoveryNotFoundError(DiscoveryError):
    """Requested content plan does not exist."""

    def __init__(self, plan_id: uuid.UUID) -> None:
        super().__init__("Content plan not found", plan_id=plan_id)


class DiscoveryConfigurationError(DiscoveryError):
    """Missing SERP key, disabled discovery, or empty topics path."""

    def __init__(
        self, message: str = "Topic discovery is not configured"
    ) -> None:
        super().__init__(message)


class DiscoveryUpstreamError(DiscoveryError):
    """SERP snapshot or topic planner failed."""


class CompetitorTopicsError(AppError):
    """Competitor-inventory content plan failed inside the application."""

    def __init__(
        self,
        message: str = "Competitor topic import failed",
        *,
        plan_id: uuid.UUID | None = None,
    ) -> None:
        self.plan_id = plan_id
        super().__init__(message)


class CompetitorTopicsNotFoundError(CompetitorTopicsError):
    """Requested competitor-gap content plan does not exist."""

    def __init__(self, plan_id: uuid.UUID) -> None:
        super().__init__("Competitor topic plan not found", plan_id=plan_id)


class CompetitorTopicsConfigurationError(CompetitorTopicsError):
    """Import is disabled or the topics file path is empty."""

    def __init__(
        self, message: str = "Competitor topic import is not configured"
    ) -> None:
        super().__init__(message)


class CompetitorTopicsParseError(CompetitorTopicsError):
    """Uploaded competitor dump could not be parsed."""

    def __init__(self, message: str = "Competitor file could not be parsed") -> None:
        super().__init__(message)


class CompetitorTopicsUpstreamError(CompetitorTopicsError):
    """Content-gap analyst failed."""
