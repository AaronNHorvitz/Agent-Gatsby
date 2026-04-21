"""Mandarin translation stage wrapper.

This module provides the Simplified Chinese stage entry point for the shared
translation pipeline. It binds the Mandarin-specific prompts, model key, and
output path while leaving chunking, cleanup, dynamic validation, and artifact
writing to :mod:`agent_gatsby.translation_common`.
"""

from __future__ import annotations

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import translate_document


def translate_mandarin(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
) -> str:
    """Translate the frozen English master into Simplified Chinese.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    english_master_text : str or None, optional
        Preloaded English master text. When omitted, the stage loads the frozen
        English master from disk.

    Returns
    -------
    str
        Final Simplified Chinese markdown written to the configured
        translation path.
    """

    return translate_document(
        config,
        stage_name="translate_mandarin",
        prompt_key="translator_zh_prompt_path",
        cleanup_prompt_key="translator_zh_cleanup_prompt_path",
        model_key="translator_zh",
        output_path=config.mandarin_translation_output_path,
        language_name="Simplified Chinese",
        source_text=english_master_text,
    )
