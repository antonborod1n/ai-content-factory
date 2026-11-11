"""Request and response schemas for client projects."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.project import Project

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectCreateRequest(BaseModel):
    """Body of POST /api/v1/projects."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=80)
    domain: str | None = None
    language: str = "ru"

    @field_validator("slug")
    @classmethod
    def slug_is_folder_safe(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if _SLUG_RE.fullmatch(cleaned) is None:
            raise ValueError("slug must be lowercase letters, digits, and hyphens")
        return cleaned

    @field_validator("language")
    @classmethod
    def language_is_ru_or_en(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"ru", "en"}:
            raise ValueError("language must be ru or en")
        return cleaned

    @field_validator("domain")
    @classmethod
    def empty_domain_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectUpdateRequest(BaseModel):
    """Body of PATCH /api/v1/projects/{id}. Slug stays fixed."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    domain: str | None = None
    language: str = "ru"

    @field_validator("name")
    @classmethod
    def name_is_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned

    @field_validator("language")
    @classmethod
    def update_language_is_ru_or_en(cls, value: str) -> str:
        return ProjectCreateRequest.language_is_ru_or_en(value)

    @field_validator("domain")
    @classmethod
    def update_domain_is_optional(cls, value: str | None) -> str | None:
        return ProjectCreateRequest.empty_domain_is_none(value)


class ProjectResponse(BaseModel):
    """One project."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    slug: str
    name: str
    domain: str | None
    language: str
    created_at: datetime


def project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        slug=project.slug,
        name=project.name,
        domain=project.domain,
        language=project.language,
        created_at=project.created_at,
    )
