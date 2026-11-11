"""Stage 5 enrichment DTOs: generated assets and internal links."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArticleAsset(BaseModel):
    """One image or infographic written next to the article (no file bytes)."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    placeholder: str
    alt: str = ""
    path: str
    status: str = "completed"


class InternalLinkRef(BaseModel):
    """One in-body link to another completed article."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url_slug: str
    anchor: str = ""


class GeneratedAsset(ArticleAsset):
    """Runtime asset including bytes for the disk write; bytes never persist."""

    model_config = ConfigDict(extra="forbid")

    data: bytes | None = Field(default=None, exclude=True)
