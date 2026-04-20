"""Spanish translation stage wrapper.

This module provides the Spanish-specific stage entry point for the translation
pipeline. It delegates the shared chunking, cleanup, dynamic validation, and
artifact-writing logic to :mod:`agent_gatsby.translation_common` while binding
the Spanish prompt and output configuration.
"""

from __future__ import annotations

from agent_gatsby.config import AppConfig
from agent_gatsby.translation_common import translate_document


def translate_spanish(
    config: AppConfig,
    *,
    english_master_text: str | None = None,
) -> str:
    """Translate the frozen English master into Spanish.

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
        Final Spanish markdown written to the configured translation path.
    """

    return translate_document(
        config,
        stage_name="translate_spanish",
        prompt_key="translator_es_prompt_path",
        cleanup_prompt_key="translator_es_cleanup_prompt_path",
        model_key="translator_es",
        output_path=config.spanish_translation_output_path,
        language_name="Spanish",
        source_text=english_master_text,
    )
