from __future__ import annotations

from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.llm_client import LLMResponseValidationError
from agent_gatsby.translate_mandarin import translate_mandarin
from agent_gatsby.translate_spanish import translate_spanish
from agent_gatsby.translation_common import (
    extract_translated_quote_lookup,
    extract_visible_citation_markers,
    freeze_english_master,
    localize_citation_metadata_line,
    normalize_translated_body,
    split_markdown_into_chunks,
)


def write_translation_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "config/prompts/translator_es.md").write_text("Translate to Spanish.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_es_cleanup.md").write_text("Clean up Spanish.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh.md").write_text("Translate to Simplified Chinese.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh_cleanup.md").write_text("Clean up Simplified Chinese.\n", encoding="utf-8")
    english_final = """# An Analysis of Metaphors in The Great Gatsby

### Introduction

Metaphor text:
> *"the green light"* [1]

Gatsby reaches for the green light [1].

### Conclusion

Nick returns to the dream and its distance [1].

## Citations

1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "In my younger and more vulnerable years my father gave me some advice...".
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
  translator_es_cleanup_prompt_path: "config/prompts/translator_es_cleanup.md"
  translator_zh_prompt_path: "config/prompts/translator_zh.md"
  translator_zh_cleanup_prompt_path: "config/prompts/translator_zh_cleanup.md"
drafting:
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
translation:
  max_chunk_chars: 80
  post_edit_body: true
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
    if "English markdown chunk:\n\n" in user_prompt:
        return user_prompt.split("English markdown chunk:\n\n", maxsplit=1)[1]
    if "Existing translated markdown chunk:\n\n" in user_prompt:
        return user_prompt.split("Existing translated markdown chunk:\n\n", maxsplit=1)[1]
    if "Existing translated markdown fragment:\n\n" in user_prompt:
        return user_prompt.split("Existing translated markdown fragment:\n\n", maxsplit=1)[1]
    if "English markdown fragment:\n\n" in user_prompt:
        return user_prompt.split("English markdown fragment:\n\n", maxsplit=1)[1]
    raise AssertionError(f"Unexpected prompt shape: {user_prompt}")


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
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert "## Citas" in translated_text
    assert '1. F. Scott Fitzgerald, *El gran Gatsby*, cap. 1, párr. 1, pasaje citado que comienza "the green light".' in translated_text
    assert any("Existing translated markdown chunk:" in prompt for prompt in prompts)


def test_translate_mandarin_writes_output(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return extract_chunk_from_prompt(kwargs["user_prompt"])

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_mandarin(config)

    assert config.mandarin_translation_output_path.exists()
    assert translated_text.startswith("# An Analysis")
    assert "## 引文" in translated_text
    assert '1. F. Scott Fitzgerald，《了不起的盖茨比》，第1章，第1段，引文开头："the green light"。' in translated_text


def test_translate_spanish_falls_back_to_fragment_stitching_when_placeholders_drift(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    calls: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        calls.append(user_prompt)
        if "English markdown chunk:" in user_prompt:
            raise LLMResponseValidationError("Translated chunk changed the citation placeholder inventory", "")
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert any("English markdown chunk:" in call for call in calls)
    assert any("English markdown fragment:" in call for call in calls)
    assert any("Existing translated markdown chunk:" in call for call in calls)


def test_translate_spanish_uses_fragment_safe_cleanup_when_cleanup_chunk_placeholders_drift(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    calls: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs["user_prompt"]
        calls.append(user_prompt)
        if "Existing translated markdown chunk:" in user_prompt:
            raise LLMResponseValidationError("Translated chunk changed the citation placeholder inventory", "")
        return extract_chunk_from_prompt(user_prompt)

    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    translated_text = translate_spanish(config)

    assert config.spanish_translation_output_path.exists()
    assert extract_visible_citation_markers(translated_text) == ["[1]", "[1]", "[1]"]
    assert any("Existing translated markdown chunk:" in call for call in calls)
    assert any("Existing translated markdown fragment:" in call for call in calls)


def test_freeze_english_master_applies_known_regression_fixes_and_writes_report(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\nThe Valley of West was a mistake, and Gatsby tried to maintain a punctiliously manner. He could still look out over the solemn dumping ground [5], hear the thin and far away [30] echoes of a dead dream, and note that a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity [6]. The ash-grey men, who move dimly and already crumbling through the powdery air [4], remain part of the landscape.\n',
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert "Valley of Ashes" in frozen
    assert "punctilious manner" in frozen
    assert '"look out over the solemn dumping ground" [5]' in frozen
    assert 'the "thin and far away" [30] echoes of a dead dream' in frozen
    assert '"a white ashen dust veiled his dark suit and his pale hair as it veiled everything in the vicinity" [6]' in frozen
    assert '"ash-grey men, who move dimly and already crumbling through the powdery air" [4]' in frozen
    report_path = repo_root / "artifacts/qa/english_master_regression_report.json"
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert '"status": "passed"' in report_text


def test_freeze_english_master_flags_unquoted_exact_quote_reuse(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\nHe refers to the great wet barnyard of Long Island Sound [3].\n',
        encoding="utf-8",
    )

    try:
        freeze_english_master(config)
    except ValueError as exc:
        assert "terminology/regression validation" in str(exc)
    else:
        raise AssertionError("freeze_english_master should reject unquoted direct quote reuse")


def test_freeze_english_master_quotes_additional_exact_quote_reuse_patterns(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_translation_repo(repo_root))
    config.final_draft_output_path.write_text(
        '# Title\n\n'
        'Gatsby is described as Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself [13]. '
        'Later the pressure rises until the straw seats of the car hovered on the edge of combustion [22]. '
        'In the hotel scene, in this heat every extra gesture was an affront to the common store of life [23]. '
        'The ending fades into a man’s voice, very thin and far away [30].\n',
        encoding="utf-8",
    )

    frozen = freeze_english_master(config)

    assert '"Jay Gatsby of West Egg, Long Island, sprang from his Platonic conception of himself" [13]' in frozen
    assert '"the straw seats of the car hovered on the edge of combustion" [22]' in frozen
    assert '"in this heat every extra gesture was an affront to the common store of life" [23]' in frozen
    assert '"a man’s voice, very thin and far away" [30]' in frozen


def test_extract_translated_quote_lookup_reads_inline_cited_quotes() -> None:
    translated = '\n'.join(
        [
            'El narrador observa «el borde deshilachado del universo» [2] en el pasaje.',
            'Más tarde, la imagen reaparece como «el gran corral húmedo de Long Island Sound» [3].',
        ]
    )

    lookup = extract_translated_quote_lookup(translated)

    assert lookup[2] == "«el borde deshilachado del universo»"
    assert lookup[3] == "«el gran corral húmedo de Long Island Sound»"


def test_localize_citation_metadata_line_uses_language_overrides_when_quote_lookup_is_missing() -> None:
    spanish_line = '29. F. Scott Fitzgerald, *The Great Gatsby*, ch. 9, para. 35, cited passage beginning "His eyes leaked continuously with excitement".'
    mandarin_line = '27. F. Scott Fitzgerald, *The Great Gatsby*, ch. 8, para. 9, cited passage beginning "It was this night that he told me the strange story of his youth...".'

    localized_spanish = localize_citation_metadata_line(spanish_line, language_name="Spanish", translated_quote_lookup={})
    localized_mandarin = localize_citation_metadata_line(
        mandarin_line,
        language_name="Simplified Chinese",
        translated_quote_lookup={},
    )

    assert "Los ojos se le llenaban continuamente de emoción" in localized_spanish
    assert "‘杰伊·盖茨比’像玻璃一样在汤姆冷酷的恶意面前碎裂了" in localized_mandarin


def test_normalize_translated_body_fixes_remaining_spanish_and_mandarin_overliteral_phrases() -> None:
    spanish = "La confrontación entre Gatsby y Tom proporciona el momento en que esta artificialidad se rompe físicamente."
    mandarin = "灰烬是如此普遍，以至于它在物理层面上改变了生活其中的人，而这种虚假性也在物理层面发生破碎的时刻显现出来。"

    normalized_spanish = normalize_translated_body(spanish, language_name="Spanish")
    normalized_mandarin = normalize_translated_body(mandarin, language_name="Simplified Chinese")

    assert "rompe físicamente" not in normalized_spanish
    assert "quiebra de forma visible" in normalized_spanish
    assert "物理层面" not in normalized_mandarin
    assert "切实地改变了生活其中的人" in normalized_mandarin
    assert "明显走向破碎的时刻" in normalized_mandarin
