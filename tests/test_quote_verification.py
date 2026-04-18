from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.verify_citations import verify_english_draft


def write_verification_repo(repo_root: Path, *, draft_text: str) -> Path:
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "artifacts/evidence").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "config").mkdir(parents=True)

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
drafting:
  output_path: "artifacts/drafts/analysis_english_draft.md"
  section_drafts_dir: "artifacts/drafts/sections"
  target_word_count_min: 2800
  target_word_count_max: 3200
  estimated_page_target: 10
  words_per_page_estimate: 280
  display_citation_format: "[#{citation_number}, Chapter {chapter}, Paragraph {paragraph}]"
  citation_appendix_heading: "Citations"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
  fail_on_quote_mismatch: true
  fail_on_invalid_citation: true
  invalid_quote_rate_threshold: 0.0
  invalid_citation_rate_threshold: 0.0
  unsupported_claim_ratio_threshold: 0.10
  normalize_curly_quotes_for_matching: true
  require_all_citations_to_resolve: true
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_verify_english_draft_passes_for_real_quotes_and_valid_locators(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    draft_text = """
# Metaphor and the Shape of Desire

## Desire at a Distance

Gatsby's "green light" turns longing into a visible object of desire [1.1].

## Material Decay and Social Vision

The "valley of ashes" gives decay a physical landscape [2.1].
""".strip() + "\n"
    config = load_config(write_verification_repo(repo_root, draft_text=draft_text))

    report = verify_english_draft(config)

    assert report.status == "passed"
    assert not report.issues
    assert report.word_count and report.word_count > 0
    assert report.estimated_pages and report.estimated_pages > 0
    assert report.quote_checks_total == 2
    assert report.quote_checks_passed == 2
    assert report.citation_checks_total == 2
    assert report.citation_checks_passed == 2
    assert report.invalid_quote_rate == 0.0
    assert report.invalid_citation_rate == 0.0
    assert report.unsupported_sentence_ratio == 0.0
    assert (repo_root / "artifacts/qa/english_verification_report.json").exists()
    registry = json.loads((repo_root / "artifacts/qa/citation_registry.json").read_text(encoding="utf-8"))
    assert registry[0]["display_label"] == "[#1, Chapter 1, Paragraph 1]"
    assert registry[1]["exact_passage_text"] == "The valley of ashes lay under the gray morning like a ruined field."


def test_verify_english_draft_accepts_human_readable_display_citations(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    draft_text = """
# Metaphor and the Shape of Desire

## Desire at a Distance

Gatsby's "green light" turns longing into a visible object of desire [#1, Chapter 1, Paragraph 1].
""".strip() + "\n"
    config = load_config(write_verification_repo(repo_root, draft_text=draft_text))

    report = verify_english_draft(config)

    assert report.status == "passed"
    registry = json.loads((repo_root / "artifacts/qa/citation_registry.json").read_text(encoding="utf-8"))
    assert registry[0]["passage_id"] == "1.1"


def test_verify_english_draft_fails_for_fake_quotes_and_invalid_locators(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    draft_text = """
# Unsupported Draft

## Desire at a Distance

Gatsby's "imaginary lantern" turns longing into something else [9.9].
""".strip() + "\n"
    config = load_config(write_verification_repo(repo_root, draft_text=draft_text))

    with pytest.raises(ValueError, match="English verification failed"):
        verify_english_draft(config)

    report = json.loads((repo_root / "artifacts/qa/english_verification_report.json").read_text(encoding="utf-8"))
    issue_codes = {issue["code"] for issue in report["issues"]}

    assert "missing_passage_locator" in issue_codes
    assert "quote_not_in_passage" in issue_codes
    assert report["status"] == "failed"
    assert report["invalid_quote_rate"] > 0.0
    assert report["invalid_citation_rate"] > 0.0
    assert report["unsupported_sentence_ratio"] > 0.0
