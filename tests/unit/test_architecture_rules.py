"""Guards for the layering rules in PROJECT.md section 14.

These tests fail if a layer starts importing something it must not know about,
which is cheaper than catching the drift in review.
"""

import ast
import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# Matches URLs that carry inline credentials, e.g. postgresql://user:pass@host.
CREDENTIALS_IN_URL_RE = re.compile(r"[a-z+]+://[^/\s\"']+:[^/@\s\"']+@")


def _module_imports(path: Path) -> set[str]:
    """Every module name referenced by import statements in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _layer_imports(*relative_dirs: str) -> dict[Path, set[str]]:
    result: dict[Path, set[str]] = {}
    for relative in relative_dirs:
        for path in (APP_DIR / relative).rglob("*.py"):
            result[path] = _module_imports(path)
    return result


def _assert_no_import_matching(
    layer: dict[Path, set[str]], prefixes: tuple[str, ...], reason: str
) -> None:
    def matches(name: str) -> bool:
        return any(
            name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes
        )

    for path, imports in layer.items():
        offenders = sorted(name for name in imports if matches(name))
        assert not offenders, f"{path.name}: {reason} (found {offenders})"


def test_openai_sdk_is_used_only_in_the_ai_layer() -> None:
    """Rule 5: OpenAI is called only through the AI layer."""
    for path in APP_DIR.rglob("*.py"):
        uses_sdk = any(
            name == "openai" or name.startswith("openai.")
            for name in _module_imports(path)
        )
        if uses_sdk:
            assert path.parent == APP_DIR / "services" / "ai", (
                f"{path.relative_to(APP_DIR)} imports the OpenAI SDK outside "
                "app/services/ai/"
            )


def test_routes_contain_no_ai_or_database_access() -> None:
    """Rules 1-2: routes do HTTP concerns only, never AI or SQL."""
    routes = _layer_imports("api/routes")
    _assert_no_import_matching(
        routes,
        ("openai", "app.services.ai", "sqlalchemy", "app.repositories", "app.db"),
        "API routes must not touch AI providers or the database directly",
    )


def test_repositories_contain_no_ai_or_service_imports() -> None:
    """Rules 3-4: repositories are database-only."""
    repositories = _layer_imports("repositories")
    _assert_no_import_matching(
        repositories,
        ("openai", "app.services", "fastapi"),
        "repositories must stay database-only",
    )


def test_service_layer_depends_on_the_writer_abstraction() -> None:
    """Rule 6: ArticleService uses AIWriter, not a concrete provider."""
    service_imports = _module_imports(APP_DIR / "services" / "article_service.py")
    assert "app.services.ai.base" in service_imports
    assert "app.services.ai.openai_writer" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)


def test_discovery_service_depends_on_abstractions() -> None:
    """SERP snapshots and clustering go through protocols, not vendors."""
    service_imports = _module_imports(APP_DIR / "services" / "discovery_service.py")
    assert "app.services.discovery.snapshotter" in service_imports
    assert "app.services.ai.topic_planner" in service_imports
    assert "app.services.discovery.serper_snapshot" not in service_imports
    assert "app.services.discovery.yandex_serpapi" not in service_imports
    assert "app.services.ai.openai_topic_planner" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)


def test_competitor_topics_service_depends_on_abstractions() -> None:
    """Gap analysis goes through ContentGapAnalyst, not a vendor client."""
    service_imports = _module_imports(
        APP_DIR / "services" / "competitor_topics_service.py"
    )
    assert "app.services.ai.content_gap" in service_imports
    assert "app.services.ai.openai_content_gap" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)


def test_research_service_depends_on_abstractions() -> None:
    """Search, fetch and outline planning go through protocols, not vendors."""
    service_imports = _module_imports(APP_DIR / "services" / "research_service.py")
    assert "app.services.research.searcher" in service_imports
    assert "app.services.research.page_fetcher" in service_imports
    assert "app.services.ai.analyst" in service_imports
    assert "app.services.research.serper_searcher" not in service_imports
    assert "app.services.ai.openai_analyst" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)


def test_pipeline_service_depends_on_abstractions() -> None:
    """Stage 4 agents go through protocols, not vendor clients."""
    service_imports = _module_imports(APP_DIR / "services" / "pipeline_service.py")
    assert "app.services.ai.seo_agent" in service_imports
    assert "app.services.ai.fact_checker" in service_imports
    assert "app.services.ai.editor" in service_imports
    assert "app.services.ai.base" in service_imports
    assert "app.services.ai.openai_seo_agent" not in service_imports
    assert "app.services.ai.openai_fact_checker" not in service_imports
    assert "app.services.ai.openai_editor" not in service_imports
    assert "app.services.ai.openai_writer" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)


def test_document_service_depends_on_the_embedder_abstraction() -> None:
    """Embeddings are called through Embedder, not a concrete provider."""
    service_imports = _module_imports(APP_DIR / "services" / "document_service.py")
    assert "app.services.ai.embedder" in service_imports
    assert "app.services.ai.openai_embedder" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)

    rag_imports = _module_imports(APP_DIR / "services" / "rag_service.py")
    assert "app.services.ai.embedder" in rag_imports
    assert "app.services.ai.openai_embedder" not in rag_imports


def test_image_service_depends_on_the_provider_abstraction() -> None:
    """Image HTTP stays behind ImageProvider."""
    service_imports = _module_imports(APP_DIR / "services" / "image_service.py")
    assert "app.services.ai.image_provider" in service_imports
    assert "app.services.ai.openai_image" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)

    article_imports = _module_imports(APP_DIR / "services" / "article_service.py")
    assert "app.services.image_service" in article_imports
    assert "app.services.linking_service" in article_imports
    assert "app.services.ai.openai_image" not in article_imports

    linking_imports = _module_imports(APP_DIR / "services" / "linking_service.py")
    assert "app.repositories.article_repository" in linking_imports
    assert "app.core.internal_links" in linking_imports
    assert not any(name.startswith("openai") for name in linking_imports)
    assert not any(name.startswith("app.services.ai") for name in linking_imports)


def test_dzen_service_depends_on_the_writer_abstraction() -> None:
    """Dzen chat stays behind DzenWriter; images reuse ImageService."""
    service_imports = _module_imports(APP_DIR / "services" / "dzen_service.py")
    assert "app.services.ai.dzen_writer" in service_imports
    assert "app.services.ai.openai_dzen" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)

    article_imports = _module_imports(APP_DIR / "services" / "article_service.py")
    assert "app.services.dzen_service" in article_imports
    assert "app.services.ai.openai_dzen" not in article_imports


def test_quality_service_depends_on_abstractions() -> None:
    """Stage 6 quality chat stays behind detector / humanizer / summarizer."""
    service_imports = _module_imports(APP_DIR / "services" / "quality_service.py")
    assert "app.services.ai.detector" in service_imports
    assert "app.services.ai.humanizer" in service_imports
    assert "app.services.ai.summarizer" in service_imports
    assert "app.services.ai.openai_detector" not in service_imports
    assert "app.services.ai.openai_humanizer" not in service_imports
    assert "app.services.ai.openai_summarizer" not in service_imports
    assert not any(name.startswith("openai") for name in service_imports)

    article_imports = _module_imports(APP_DIR / "services" / "article_service.py")
    assert "app.services.quality_service" in article_imports
    assert "app.services.ai.openai_detector" not in article_imports
    assert "app.services.ai.openai_humanizer" not in article_imports
    assert "app.services.ai.openai_summarizer" not in article_imports


def test_core_quality_is_deterministic() -> None:
    """Verdict helpers stay in core: no AI, no SQL."""
    imports = _module_imports(APP_DIR / "core" / "quality.py")
    assert "sqlalchemy" not in imports
    assert "openai" not in imports
    assert not any(name.startswith("app.services") for name in imports)
    assert not any(name.startswith("app.repositories") for name in imports)


def test_core_enrichment_modules_are_deterministic() -> None:
    """Placeholder parse and link insertion stay in core: no AI, no SQL."""
    for relative in (
        "core/placeholders.py",
        "core/internal_links.py",
        "core/section_images.py",
        "core/page_structure.py",
        "core/competitor_brief.py",
        "core/competitor_filter.py",
        "core/http_url.py",
        "core/topic_candidates.py",
        "core/competitor_plan.py",
        "core/competitor_sources.py",
        "core/topic_source.py",
        "core/run_log.py",
    ):
        imports = _module_imports(APP_DIR / relative)
        assert "sqlalchemy" not in imports
        assert "openai" not in imports
        assert not any(name.startswith("app.services") for name in imports)
        assert not any(name.startswith("app.repositories") for name in imports)


def test_prompts_are_not_embedded_in_python() -> None:
    """Rule: prompt text lives in prompts/, not in code."""
    ai_dir = APP_DIR / "services" / "ai"
    for path in ai_dir.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "You are " not in source, (
            f"{path.name} looks like it embeds prompt text; move it to prompts/"
        )


@pytest.mark.parametrize("secret", ["sk-", "OPENAI_API_KEY="])
def test_no_hardcoded_secrets_in_application_code(secret: str) -> None:
    """Rule 8: secrets live only in environment variables."""
    for path in APP_DIR.rglob("*.py"):
        assert secret not in path.read_text(encoding="utf-8"), (
            f"{path.relative_to(APP_DIR)} must not hardcode {secret!r}"
        )


def test_no_connection_credentials_in_application_code() -> None:
    """Any `scheme://user:password@host` literal is a leaked credential."""
    for path in APP_DIR.rglob("*.py"):
        match = CREDENTIALS_IN_URL_RE.search(path.read_text(encoding="utf-8"))
        assert match is None, (
            f"{path.relative_to(APP_DIR)} embeds connection credentials: "
            f"{match.group(0) if match else ''}"
        )
