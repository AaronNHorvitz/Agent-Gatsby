from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.plan_outline import plan_outline


def write_outline_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/evidence").mkdir(parents=True)
    (repo_root / "config/prompts/outline.md").write_text("Output JSON only.\n", encoding="utf-8")

    evidence_records = [
        {
            "evidence_id": "E001",
            "metaphor": "green light",
            "quote": "green light",
            "passage_id": "1.1",
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
            "passage_id": "2.1",
            "chapter": 2,
            "interpretation": "A material landscape that turns moral decay into a visible social metaphor.",
            "supporting_theme_tags": ["class", "decay"],
            "status": "verified",
            "source_candidate_id": "C002",
            "source_type": "candidate",
        },
    ]
    (repo_root / "artifacts/evidence/evidence_ledger.json").write_text(
        json.dumps(evidence_records, indent=2, ensure_ascii=False) + "\n",
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
  outline_prompt_path: "config/prompts/outline.md"
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
  fixed_title: "An Analysis of Metaphors in The Great Gatsby"
  require_intro: true
  require_conclusion: true
  require_thesis: true
  require_evidence_ids_per_section: true
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_plan_outline_writes_outline_with_valid_evidence_ids(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_outline_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return json.dumps(
            {
                "title": "Some Other Title",
                "thesis": "Fitzgerald's metaphors turn longing, class decay, and idealization into visible structures.",
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
        )

    monkeypatch.setattr("agent_gatsby.plan_outline.invoke_text_completion", fake_invoke_text_completion)
    outline = plan_outline(config)

    outline_path = repo_root / "artifacts/drafts/outline.json"
    assert outline_path.exists()
    assert outline.title == "An Analysis of Metaphors in The Great Gatsby"
    assert outline.thesis
    assert len(outline.sections) == 2

    saved_outline = json.loads(outline_path.read_text(encoding="utf-8"))
    assert saved_outline["title"] == "An Analysis of Metaphors in The Great Gatsby"
    assert saved_outline["sections"]
    assert saved_outline["sections"][0]["evidence_ids"] == ["E001"]
    assert saved_outline["sections"][1]["evidence_ids"] == ["E002"]


def test_plan_outline_rejects_nonexistent_evidence_ids(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_outline_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return json.dumps(
            {
                "title": "Unsupported Outline",
                "thesis": "The outline should fail if it references missing evidence.",
                "intro_notes": "Set up the problem.",
                "sections": [
                    {
                        "section_id": "S1",
                        "heading": "Missing Support",
                        "evidence_ids": ["E999"],
                    },
                    {
                        "section_id": "S2",
                        "heading": "Still Missing Support",
                        "evidence_ids": ["E001"],
                    },
                ],
                "conclusion_notes": "This should not be written.",
            }
        )

    monkeypatch.setattr("agent_gatsby.plan_outline.invoke_text_completion", fake_invoke_text_completion)

    with pytest.raises(ValueError, match="Outline references missing evidence ID: E999"):
        plan_outline(config)

    assert not (repo_root / "artifacts/drafts/outline.json").exists()
