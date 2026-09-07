"""AI abstractions for article generation."""

from app.services.ai.base import AIWriter
from app.services.ai.mock_writer import MockAIWriter
from app.services.ai.openai_writer import OpenAIWriter
from app.services.ai.prompt_loader import (
    load_prompt,
    load_system_prompt,
    render_article_writer_prompt,
)

__all__ = [
    "AIWriter",
    "MockAIWriter",
    "OpenAIWriter",
    "load_prompt",
    "load_system_prompt",
    "render_article_writer_prompt",
]
