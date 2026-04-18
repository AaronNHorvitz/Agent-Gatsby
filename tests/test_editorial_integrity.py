from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.critique_and_edit import build_editorial_response_validator, critique_and_edit
from agent_gatsby.llm_client import LLMResponseValidationError


def write_editorial_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "artifacts/evidence").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "config/prompts/critic.md").write_text("Output revised markdown only.\n", encoding="utf-8")

    passage_index = {
        "source_name": "gatsby_locked",
        "normalized_path": "data/normalized/gatsby_locked.txt",
        "chapter_count": 2,
        "passage_count": 2,
        "generated_at": "2026-04-18T00:00:00Z",
        "passages": [
            {
                "passage_id": "1.1",
                "chapter": 1,
                "paragraph": 1,
                "text": "Gatsby reached toward the green light at the end of the dock.",
                "char_start": 0,
                "char_end": 58,
            },
            {
                "passage_id": "2.1",
                "chapter": 2,
                "paragraph": 1,
                "text": "The valley of ashes lay under the gray morning like a ruined field.",
                "char_start": 60,
                "char_end": 129,
            },
        ],
    }
    evidence_records = [
        {
            "evidence_id": "E001",
            "metaphor": "green light",
            "quote": "green light",
            "passage_id": "1.1",
            "chapter": 1,
            "interpretation": "A recurring image that concentrates Gatsby's longing into a distant object.",
            "supporting_theme_tags": [],
            "status": "verified",
            "source_candidate_id": "C001",
            "source_type": "candidate",
        },
        {
            "evidence_id": "E002",
            "metaphor": "valley of ashes",
            "quote": "valley of ashes",
            "passage_id": "2.1",
            "chapter": 2,
            "interpretation": "A social metaphor for material and moral decay.",
            "supporting_theme_tags": [],
            "status": "verified",
            "source_candidate_id": "C002",
            "source_type": "candidate",
        },
    ]
    draft_text = "\n".join(
        [
            "# Metaphor and the Shape of Desire",
            "",
            "## Introduction",
            "",
            "The essay opens by framing metaphor as a structural device.",
            "",
            "## Desire at a Distance",
            "",
            'Gatsby\'s "green light" turns longing into a visible object of desire [1.1].',
            "",
            "## Material Decay and Social Vision",
            "",
            'The "valley of ashes" gives decay a physical landscape [2.1].',
            "",
            "## Conclusion",
            "",
            'Together, the "green light" and the "valley of ashes" define the essay\'s closing contrast [1.1] [2.1].',
            "",
        ]
    )

    (repo_root / "artifacts/manifests/passage_index.json").write_text(
        json.dumps(passage_index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts/evidence/evidence_ledger.json").write_text(
        json.dumps(evidence_records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts/drafts/analysis_english_draft.md").write_text(draft_text, encoding="utf-8")

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
  preserve_chapter_markers: true
  collapse_excessive_blank_lines: true
  strip_leading_trailing_whitespace: true
models:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"
  primary_reasoner: "gemma4:26b"
  timeout_seconds: 1
  max_retries: 0
  retry_backoff_seconds: 0
llm_defaults:
  temperature: 0.2
  top_p: 0.9
  max_tokens: 512
prompts:
  critic_prompt_path: "config/prompts/critic.md"
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
  remove_empty_paragraphs: true
  passage_id_format: "{chapter}.{paragraph}"
extraction:
  output_path: "artifacts/evidence/metaphor_candidates.json"
  raw_debug_output_path: "artifacts/evidence/metaphor_candidates_raw.txt"
evidence_ledger:
  output_path: "artifacts/evidence/evidence_ledger.json"
  rejected_output_path: "artifacts/evidence/rejected_candidates.json"
outline:
  fixed_title: "An Analysis of Metaphors in The Great Gatsby"
drafting:
  output_path: "artifacts/drafts/analysis_english_draft.md"
  section_drafts_dir: "artifacts/drafts/sections"
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
  display_citation_format: "[{citation_number}]"
  citation_appendix_heading: "Citations"
  citation_text_title: "Citation Text"
  citation_text_output_path: "artifacts/final/citation_text.md"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
  fail_on_quote_mismatch: true
  fail_on_invalid_citation: true
  normalize_curly_quotes_for_matching: true
  require_all_citations_to_resolve: true
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_critique_and_edit_writes_final_file_and_preserves_integrity(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_editorial_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        revised = "\n".join(
            [
                "# Metaphor and the Shape of Desire",
                "",
                "## Introduction",
                "",
                "The essay opens by framing metaphor as a structural device that coordinates the later sections more clearly.",
                "",
                "## Desire at a Distance",
                "",
                'Gatsby\'s "green light" turns longing into a visible object of desire [1.1].',
                "",
                "## Material Decay and Social Vision",
                "",
                'The "valley of ashes" gives decay a physical landscape while tightening the paragraph\'s transition [2.1].',
                "",
                "## Conclusion",
                "",
                'Together, the "green light" and the "valley of ashes" define the essay\'s closing contrast [1.1] [2.1].',
                "",
            ]
        )
        validator = kwargs.get("response_validator")
        if validator is not None:
            validator(revised)
        return revised

    monkeypatch.setattr("agent_gatsby.critique_and_edit.invoke_text_completion", fake_invoke_text_completion)

    final_text = critique_and_edit(config)

    final_path = repo_root / "artifacts/drafts/analysis_english_final.md"
    citation_text_path = repo_root / "artifacts/final/citation_text.md"
    assert final_path.exists()
    assert citation_text_path.exists()
    assert '*"green light"*' in final_text
    assert '*"valley of ashes"*' in final_text
    assert "[1]" in final_text
    assert "[2]" in final_text
    assert "## Citations" not in final_text
    assert "# An Analysis of Metaphors in The Great Gatsby" in final_text
    citation_text = citation_text_path.read_text(encoding="utf-8")
    assert "# Citation Text" in citation_text
    assert "## [1]" in citation_text
    assert "Chapter 1, Paragraph 1" in citation_text
    assert (repo_root / "artifacts/qa/english_verification_report.json").exists()
    assert (repo_root / "artifacts/qa/citation_registry.json").exists()


def test_editorial_response_validator_rejects_changed_quotes_and_citations() -> None:
    original_text = "\n".join(
        [
            "# Sample Essay",
            "",
            "## Body",
            "",
            'Gatsby\'s "green light" remains central [1.1].',
            "",
        ]
    )
    validator = build_editorial_response_validator(original_text)

    with pytest.raises(ValueError, match="citation marker inventory"):
        validator(
            "\n".join(
                [
                    "# Sample Essay",
                    "",
                    "## Body",
                    "",
                    'Gatsby\'s "green light" remains central [2.1].',
                    "",
                ]
            )
        )

    with pytest.raises(ValueError, match="direct-quote inventory"):
        validator(
            "\n".join(
                [
                    "# Sample Essay",
                    "",
                    "## Body",
                    "",
                    'Gatsby\'s "beacon" remains central [1.1].',
                    "",
                ]
            )
        )


def test_critique_and_edit_falls_back_to_verified_draft_when_editor_returns_empty(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_editorial_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        raise LLMResponseValidationError("Model returned empty content", "")

    monkeypatch.setattr("agent_gatsby.critique_and_edit.invoke_text_completion", fake_invoke_text_completion)

    final_text = critique_and_edit(config)
    assert 'Gatsby\'s *"green light"* turns longing into a visible object of desire [1].' in final_text
    assert "## Citations" not in final_text
    assert (repo_root / "artifacts/final/citation_text.md").exists()
    assert (repo_root / "artifacts/drafts/analysis_english_final.md").read_text(encoding="utf-8").strip() == final_text.strip()
