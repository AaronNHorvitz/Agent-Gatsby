"""
Spanish translation stage for Agent Gatsby.
"""

from __future__ import annotations

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import translate_document


def translate_spanish(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
) -> str:
    return translate_document(
        config,
        stage_name="translate_spanish",
        prompt_key="translator_es_prompt_path",
        model_key="translator_es",
        output_path=config.spanish_translation_output_path,
        language_name="Spanish",
        source_text=english_master_text,
    )
