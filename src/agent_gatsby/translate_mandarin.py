"""
Mandarin translation stage for Agent Gatsby.
"""

from __future__ import annotations

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import translate_document


def translate_mandarin(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
) -> str:
    return translate_document(
        config,
        stage_name="translate_mandarin",
        prompt_key="translator_zh_prompt_path",
        model_key="translator_zh",
        output_path=config.mandarin_translation_output_path,
        language_name="Simplified Chinese",
        source_text=english_master_text,
    )
