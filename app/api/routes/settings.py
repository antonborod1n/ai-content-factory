"""Read-only operator settings: runtime status and prompt text."""

from fastapi import APIRouter, HTTPException, status

from app.core.prompt_catalog import list_prompt_filenames, read_prompt_filename
from app.core.runtime_status import runtime_status
from app.schemas.settings import PromptDetail, PromptListItem, RuntimeStatus

router = APIRouter(tags=["settings"])


@router.get("/settings/runtime", response_model=RuntimeStatus)
async def get_runtime_status() -> RuntimeStatus:
    return RuntimeStatus.model_validate(runtime_status())


@router.get("/prompts", response_model=list[PromptListItem])
async def list_prompts() -> list[PromptListItem]:
    return [PromptListItem(filename=name) for name in list_prompt_filenames()]


@router.get("/prompts/{filename}", response_model=PromptDetail)
async def get_prompt(filename: str) -> PromptDetail:
    try:
        content = read_prompt_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found",
        ) from exc
    return PromptDetail(filename=filename, content=content)
