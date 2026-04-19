from __future__ import annotations

from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.llm_client import LLMResponseValidationError
from agent_gatsby.translate_mandarin import translate_mandarin
from agent_gatsby.translate_spanish import translate_spanish
from agent_gatsby.translation_common import extract_visible_citation_markers, split_markdown_into_chunks


def write_translation_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "config/prompts/translator_es.md").write_text("Translate to Spanish.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh.md").write_text("Translate to Simplified Chinese.\n", encoding="utf-8")
    english_final = """# An Analysis of Metaphors in The Great Gatsby

### Introduction

Gatsby reaches for *"the green light"* [1].

### Conclusion

Nick returns to the dream and its distance [1].
"""
    (repo_root / "artifacts/drafts/analysis_english_final.md").write_text(english_final, encoding="utf-8")

    config_text = """
paths:
  repo_root: "."
  config_dir: "config"
  source_dir: "data/source"
  normalized_dir: "data/normalized"
  artifacts_dir: "artifacts"
  manifests_dir: "artifacts/manifests"
  evidence_dir: "artifacts/evidence"
  drafts_dir: "artifacts/drafts"
  final_dir: "artifacts/final"
  translations_dir: "artifacts/translations"
  qa_dir: "artifacts/qa"
  logs_dir: "artifacts/logs"
  outputs_dir: "outputs"
  fonts_dir: "fonts"
source:
  file_path: "data/source/gatsby_source.txt"
  normalized_output_path: "data/normalized/gatsby_locked.txt"
  manifest_output_path: "artifacts/manifests/source_manifest.json"
  encoding: "utf-8"
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
models:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"
  primary_reasoner: "gemma4:26b"
  translator_es: "gemma4:26b"
  translator_zh: "gemma4:26b"
  timeout_seconds: 1
  max_retries: 0
  retry_backoff_seconds: 0
llm_defaults:
  temperature: 0.2
  top_p: 0.9
  max_tokens: 512
prompts:
  translator_es_prompt_path: "config/prompts/translator_es.md"
  translator_zh_prompt_path: "config/prompts/translator_zh.md"
drafting:
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
translation:
  max_chunk_chars: 80
  preserve_headings: true
  preserve_citations: true
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def extract_chunk_from_prompt(user_prompt: str) -> str:
    return user_prompt.split("English markdown chunk:\n\n", maxsplit=1)[1]


def test_split_markdown_into_chunks_preserves_block_boundaries() -> None:
    text = "# Title\n\n## One\n\nAlpha beta gamma.\n\n## Two\n\nDelta epsilon zeta."
    chunks = split_markdown_into_chunks(text, max_chars=30)

    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    assert chunks[0].startswith("# Title")


def test_translate_spanish_freezes_master_and_preserves_citations(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    prompts: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        prompts.append(user_prompt)
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.english_master_output_path.exists()
    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]"]
    assert len(prompts) >= 2


def test_translate_mandarin_writes_output(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return extract_chunk_from_prompt(kwargs["user_prompt"])

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_mandarin(config)

    assert config.mandarin_translation_output_path.exists()
    assert translated_text.startswith("# An Analysis")


def test_translate_spanish_falls_back_to_fragment_stitching_when_placeholders_drift(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    calls: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        calls.append(user_prompt)
        if "English markdown chunk:" in user_prompt:
            raise LLMResponseValidationError("Translated chunk changed the citation placeholder inventory", "")
        return user_prompt.split("English markdown fragment:\n\n", maxsplit=1)[1]

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]"]
    assert any("English markdown chunk:" in call for call in calls)
    assert any("English markdown fragment:" in call for call in calls)
