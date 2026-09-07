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
