from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.draft_english import build_section_response_validator, draft_english
from agent_gatsby.llm_client import LLMResponseValidationError
from agent_gatsby.schemas import EvidenceRecord


def write_draft_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/evidence").mkdir(parents=True)
    (repo_root / "artifacts/drafts").mkdir(parents=True)
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "config/prompts/draft.md").write_text("Output markdown only.\n", encoding="utf-8")

    passage_index = {
        "source_name": "gatsby_locked",
        "normalized_path": "data/normalized/gatsby_locked.txt",
        "chapter_count": 2,
        "passage_count": 4,
        "generated_at": "2026-04-18T00:00:00Z",
        "passages": [
            {
                "passage_id": "1.1",
                "chapter": 1,
                "paragraph": 1,
                "text": "Nick arrives with a cautious sense of distance from the East.",
                "char_start": 0,
                "char_end": 58,
            },
            {
                "passage_id": "1.2",
                "chapter": 1,
                "paragraph": 2,
                "text": "Gatsby reached toward the green light at the end of the dock.",
                "char_start": 60,
                "char_end": 118,
            },
            {
                "passage_id": "2.1",
                "chapter": 2,
                "paragraph": 1,
                "text": "Ashes spread outward beneath the billboard and the road.",
                "char_start": 120,
                "char_end": 178,
            },
            {
                "passage_id": "2.2",
                "chapter": 2,
                "paragraph": 2,
                "text": "The valley of ashes gives decay a physical landscape.",
                "char_start": 180,
                "char_end": 234,
            },
        ],
    }
    (repo_root / "artifacts/manifests/passage_index.json").write_text(
        json.dumps(passage_index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    evidence_records = [
        {
            "evidence_id": "E001",
            "metaphor": "green light",
            "quote": "green light",
            "passage_id": "1.2",
            "chapter": 1,
            "interpretation": "A recurring image that concentrates Gatsby's longing into a distant object.",
            "supporting_theme_tags": ["desire"],
            "status": "verified",
            "source_candidate_id": "C001",
            "source_type": "candidate",
        },
        {
            "evidence_id": "E002",
            "metaphor": "valley of ashes",
            "quote": "valley of ashes",
            "passage_id": "2.2",
            "chapter": 2,
            "interpretation": "A material landscape that turns moral decay into a visible social metaphor.",
            "supporting_theme_tags": ["class", "decay"],
            "status": "verified",
            "source_candidate_id": "C002",
            "source_type": "candidate",
        },
    ]
    outline = {
        "title": "Metaphor and the Shape of Desire",
        "thesis": "Fitzgerald's metaphors turn longing and decay into visible structures.",
        "intro_notes": "Introduce metaphor as an organizing device.",
        "sections": [
            {
                "section_id": "S1",
                "heading": "Desire at a Distance",
                "evidence_ids": ["E001"],
            },
            {
                "section_id": "S2",
                "heading": "Material Decay and Social Vision",
                "evidence_ids": ["E002"],
            },
        ],
        "conclusion_notes": "Return to the collapse of Gatsby's idealized vision.",
    }
    (repo_root / "artifacts/evidence/evidence_ledger.json").write_text(
        json.dumps(evidence_records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (repo_root / "artifacts/drafts/outline.json").write_text(
        json.dumps(outline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

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
  draft_prompt_path: "config/prompts/draft.md"
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
  output_path: "artifacts/drafts/outline.json"
  minimum_section_count: 2
  maximum_section_count: 4
  require_intro: true
  require_conclusion: true
  require_thesis: true
  require_evidence_ids_per_section: true
drafting:
  output_path: "artifacts/drafts/analysis_english_draft.md"
  section_drafts_dir: "artifacts/drafts/sections"
  final_output_path: "artifacts/drafts/analysis_english_final.md"
  master_output_path: "artifacts/final/analysis_english_master.md"
  target_word_count_min: 2800
  target_word_count_max: 3200
  estimated_page_target: 10
  words_per_page_estimate: 280
  display_citation_format: "[#{citation_number}, Chapter {chapter}, Paragraph {paragraph}]"
  citation_appendix_heading: "Citations"
  context_window_paragraphs_before: 1
  context_window_paragraphs_after: 1
  write_section_by_section: true
  max_evidence_per_section: 4
  citation_format: "[{passage_id}]"
  preserve_direct_quotes: true
  forbid_invented_citations: true
  forbid_invented_quotes: true
  target_tone: "formal academic literary analysis"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_draft_english_writes_section_files_and_combined_markdown(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_draft_repo(repo_root))
    prompt_checks = {
        "overall_target": False,
        "section_target": False,
        "context_payload": False,
        "scene_guidance": False,
        "body_structure": False,
        "intro_style": False,
        "body_argument_context": False,
    }
    call_order: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs.get("user_prompt", "")
        if "Overall essay target: about 2800-3200 words; roughly 10 pages at about 280 words per page." in user_prompt:
            prompt_checks["overall_target"] = True
        if "Target section length:" in user_prompt:
            prompt_checks["section_target"] = True
        if '"previous_passages": [' in user_prompt and '"cited_passage": {' in user_prompt:
            prompt_checks["context_payload"] = True
        if "Ground the analysis in what the text is doing in the current scene" in user_prompt:
            prompt_checks["scene_guidance"] = True
        if "opening claim, quoted supporting evidence with citation" in user_prompt:
            prompt_checks["body_structure"] = True
        if "F. Scott Fitzgerald's writing style" in user_prompt:
            prompt_checks["intro_style"] = True
        if "Completed body arguments:" in user_prompt:
            prompt_checks["body_argument_context"] = True
        if "Section type: introduction" in user_prompt:
            call_order.append("introduction")
            return (
                "F. Scott Fitzgerald writes in a style that turns emotion and ambition into images the reader can see. "
                "In The Great Gatsby, he uses metaphor to make desire and decay feel concrete while the novel follows characters chasing wealth, love, and status. "
                "This essay examines two selected metaphors to fit the assignment length, and the first body section begins with Gatsby's distant vision of desire."
            )
        if "Section heading: Desire at a Distance" in user_prompt:
            call_order.append("body:S1")
            return (
                'This section argues that Gatsby\'s "green light" turns longing into a visible destination [1.2]. '
                'The quoted image gives the reader a concrete object that carries Gatsby\'s desire in scene context [1.2]. '
                'That visible distance prepares the essay to move from desire to decay.'
            )
        if "Section heading: Material Decay and Social Vision" in user_prompt:
            call_order.append("body:S2")
            return (
                'This section argues that the "valley of ashes" turns moral damage into a physical landscape [2.2]. '
                'The quoted image proves that Fitzgerald makes social decay visible in the scene itself [2.2]. '
                'That shift from desire to ruin sets up the conclusion.'
            )
        call_order.append("conclusion")
        return "The conclusion gathers the essay's claims into a final judgment about Fitzgerald's metaphors."

    monkeypatch.setattr("agent_gatsby.draft_english.invoke_text_completion", fake_invoke_text_completion)

    draft_text = draft_english(config)

    assert (repo_root / "artifacts/drafts/analysis_english_draft.md").exists()
    assert (repo_root / "artifacts/drafts/sections/S1.md").exists()
    assert (repo_root / "artifacts/drafts/sections/S2.md").exists()
    assert "_This report analyzes 2 selected metaphors" in draft_text
    assert "## Introduction" in draft_text
    assert "## Desire at a Distance" in draft_text
    assert "## Material Decay and Social Vision" in draft_text
    assert 'Metaphor text:\n> "green light" [1.2]' in draft_text
    assert 'Metaphor text:\n> "valley of ashes" [2.2]' in draft_text
    assert "[1.2]" in draft_text
    assert "[2.2]" in draft_text
    assert prompt_checks["overall_target"] is True
    assert prompt_checks["section_target"] is True
    assert prompt_checks["context_payload"] is True
    assert prompt_checks["scene_guidance"] is True
    assert prompt_checks["body_structure"] is True
    assert prompt_checks["intro_style"] is True
    assert prompt_checks["body_argument_context"] is True
    assert call_order == ["body:S1", "body:S2", "introduction", "conclusion"]


def test_draft_english_retries_introduction_with_compact_prompt(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_draft_repo(repo_root))
    call_log: list[str] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        user_prompt = kwargs.get("user_prompt", "")
        call_log.append(user_prompt)
        if "Compact retry mode: introductory summary only." in user_prompt:
            return (
                "The novel follows Nick Carraway as he watches Gatsby pursue an idealized vision of love and status. "
                "Fitzgerald uses metaphor to make desire, decay, and distance easier to see.\n\n"
                "These two selected metaphors were chosen to fit the assignment length while still showing how the novel turns longing and social damage into concrete images."
            )
        if "Section type: introduction" in user_prompt:
            raise LLMResponseValidationError(
                "Model returned empty content (finish_reason=length, reasoning_len=22)",
                "",
            )
        if "Section heading: Desire at a Distance" in user_prompt:
            return 'In this scene, Gatsby\'s "green light" turns longing into a visible object of desire [1.2].'
        if "Section heading: Material Decay and Social Vision" in user_prompt:
            return 'In this scene, the "valley of ashes" gives moral decay a physical landscape [2.2].'
        return "The conclusion gathers the essay's claims into a final judgment."

    monkeypatch.setattr("agent_gatsby.draft_english.invoke_text_completion", fake_invoke_text_completion)

    draft_text = draft_english(config)

    assert "The novel follows Nick Carraway" in draft_text
    assert any("Compact retry mode: introductory summary only." in prompt for prompt in call_log)
    assert any("Do not use any direct quotations or quotation marks in this introduction" in prompt for prompt in call_log)
    assert any("Completed body arguments:" in prompt for prompt in call_log)
    assert any("Section type: introduction" in prompt for prompt in call_log)


def test_section_response_validator_rejects_paraphrase_quotes_and_bad_locators() -> None:
    evidence_records = [
        EvidenceRecord(
            evidence_id="E001",
            metaphor="green light",
            quote="green light",
            passage_id="1.2",
            chapter=1,
            interpretation="A recurring image that concentrates Gatsby's longing into a distant object.",
            supporting_theme_tags=[],
            status="verified",
            source_candidate_id="C001",
            source_type="candidate",
        )
    ]
    validator = build_section_response_validator(evidence_records, require_citation=True)

    with pytest.raises(ValueError, match="quoted text outside the allowed evidence set"):
        validator('Gatsby\'s "visible beacon" marks desire [1.2].')

    with pytest.raises(ValueError, match="citations outside the allowed evidence set"):
        validator('Gatsby\'s "green light" marks desire [9.9].')
