"""AI abstractions for article generation."""

from app.services.ai.analyst import CompetitorAnalyst
from app.services.ai.base import AIWriter
from app.services.ai.content_gap import ContentGapAnalyst
from app.services.ai.detector import AiDetector
from app.services.ai.dzen_writer import DzenWriter
from app.services.ai.editor import Editor
from app.services.ai.embedder import Embedder
from app.services.ai.fact_checker import FactChecker
from app.services.ai.humanizer import Humanizer
from app.services.ai.image_provider import ImageProvider
from app.services.ai.mock_analyst import MockCompetitorAnalyst
from app.services.ai.mock_content_gap import MockContentGapAnalyst
from app.services.ai.mock_detector import MockAiDetector
from app.services.ai.mock_dzen import MockDzenWriter
from app.services.ai.mock_editor import MockEditor
from app.services.ai.mock_embedder import MockEmbedder
from app.services.ai.mock_fact_checker import MockFactChecker
from app.services.ai.mock_humanizer import MockHumanizer
from app.services.ai.mock_image import MockImageProvider
from app.services.ai.mock_seo_agent import MockSeoAgent
from app.services.ai.mock_summarizer import MockSummarizer
from app.services.ai.mock_topic_planner import MockTopicPlanner
from app.services.ai.mock_writer import MockAIWriter
from app.services.ai.openai_analyst import OpenAICompetitorAnalyst
from app.services.ai.openai_content_gap import OpenAIContentGapAnalyst
from app.services.ai.openai_detector import OpenAIDetector
from app.services.ai.openai_dzen import OpenAIDzenWriter
from app.services.ai.openai_editor import OpenAIEditor
from app.services.ai.openai_embedder import OpenAIEmbedder
from app.services.ai.openai_fact_checker import OpenAIFactChecker
from app.services.ai.openai_humanizer import OpenAIHumanizer
from app.services.ai.openai_image import OpenAIImageProvider
from app.services.ai.openai_seo_agent import OpenAISeoAgent
from app.services.ai.openai_summarizer import OpenAISummarizer
from app.services.ai.openai_topic_planner import OpenAITopicPlanner
from app.services.ai.openai_writer import OpenAIWriter
from app.services.ai.prompt_loader import (
    load_prompt,
    load_system_prompt,
    render_article_writer_prompt,
)
from app.services.ai.seo_agent import SeoAgent
from app.services.ai.summarizer import Summarizer
from app.services.ai.topic_planner import TopicPlanner

__all__ = [
    "AIWriter",
    "AiDetector",
    "CompetitorAnalyst",
    "ContentGapAnalyst",
    "DzenWriter",
    "Editor",
    "Embedder",
    "FactChecker",
    "Humanizer",
    "ImageProvider",
    "MockAIWriter",
    "MockAiDetector",
    "MockCompetitorAnalyst",
    "MockContentGapAnalyst",
    "MockDzenWriter",
    "MockEditor",
    "MockEmbedder",
    "MockFactChecker",
    "MockHumanizer",
    "MockImageProvider",
    "MockSeoAgent",
    "MockSummarizer",
    "MockTopicPlanner",
    "OpenAICompetitorAnalyst",
    "OpenAIContentGapAnalyst",
    "OpenAIDetector",
    "OpenAIDzenWriter",
    "OpenAIEditor",
    "OpenAIEmbedder",
    "OpenAIFactChecker",
    "OpenAIHumanizer",
    "OpenAIImageProvider",
    "OpenAISeoAgent",
    "OpenAISummarizer",
    "OpenAITopicPlanner",
    "OpenAIWriter",
    "SeoAgent",
    "Summarizer",
    "TopicPlanner",
    "load_prompt",
    "load_system_prompt",
    "render_article_writer_prompt",
]
