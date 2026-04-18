from __future__ import annotations

import json
from pathlib import Path

from agent_gatsby.build_evidence_ledger import build_evidence_ledger
from agent_gatsby.config import load_config
from agent_gatsby.schemas import PassageIndex, PassageRecord


def write_evidence_repo(repo_root: Path) -> Path:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "artifacts/evidence").mkdir(parents=True)

    passage_index = PassageIndex(
        source_name="gatsby_locked",
        normalized_path="data/normalized/gatsby_locked.txt",
        chapter_count=1,
        passage_count=2,
        generated_at="2026-04-18T00:00:00Z",
        passages=[
            PassageRecord(
                passage_id="1.1",
                chapter=1,
                paragraph=1,
                text="Gatsby reached toward the green light at the end of the dock.",
                char_start=0,
                char_end=58,
            ),
            PassageRecord(
                passage_id="1.2",
                chapter=1,
                paragraph=2,
                text="The water between him and the light looked like a dark promise.",
                char_start=60,
                char_end=126,
            ),
        ],
    )
    (repo_root / "artifacts/manifests/passage_index.json").write_text(
        json.dumps(passage_index.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates = [
        {
            "candidate_id": "C009",
            "label": "  Green   Light ",
            "passage_id": "1.1",
            "quote": "green light",
            "rationale": "A recurring image that concentrates Gatsby's longing into a visible, distant object.",
            "confidence": 0.95,
        },
        {
            "candidate_id": "C010",
            "label": "dark promise",
            "passage_id": "1.2",
            "quote": "missing quote",
            "rationale": "Too vague",
            "confidence": 0.41,
        },
        {
            "candidate_id": "C011",
            "label": "ghost image",
            "passage_id": "9.9",
            "quote": "ghost image",
            "rationale": "A recurring image that shapes the novel's emotional distance.",
            "confidence": 0.50,
        },
    ]
    (repo_root / "artifacts/evidence/metaphor_candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + "\n",
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
  target_verified_record_count: 3
  require_exact_quote_match: true
  reject_missing_passage_ids: true
  reject_empty_rationales: true
  minimum_quote_length: 8
  status_for_verified_entries: "verified"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_build_evidence_ledger_promotes_valid_candidates_and_writes_rejections(tmp_path, caplog) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_evidence_repo(repo_root))

    evidence_records, rejected_candidates = build_evidence_ledger(config)

    ledger_path = repo_root / "artifacts/evidence/evidence_ledger.json"
    rejected_path = repo_root / "artifacts/evidence/rejected_candidates.json"

    assert ledger_path.exists()
    assert rejected_path.exists()
    assert len(evidence_records) == 1
    assert len(rejected_candidates) == 2
    assert evidence_records[0].passage_id == "1.1"
    assert evidence_records[0].quote == "green light"
    assert evidence_records[0].status == "verified"
    assert evidence_records[0].metaphor == "green light"
    ledger_text = ledger_path.read_text(encoding="utf-8")
    rejected_text = rejected_path.read_text(encoding="utf-8")
    assert '"source_candidate_id": "C009"' in ledger_text
    assert "Quote does not exact-match the source passage" in rejected_text
    assert "Passage ID does not exist in passage index" in rejected_text
    assert "Verified evidence count is below target" in caplog.text
