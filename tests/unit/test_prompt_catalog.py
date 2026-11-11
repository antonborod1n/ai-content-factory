"""Prompt catalog stays inside the prompts folder."""

import pytest

from app.core.prompt_catalog import read_prompt_filename


def test_prompt_name_cannot_leave_the_folder() -> None:
    with pytest.raises(ValueError):
        read_prompt_filename("../.env")
    with pytest.raises(ValueError):
        read_prompt_filename("article_writer.md/../../.env")
