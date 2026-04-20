from __future__ import annotations

import json
from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.extract_metaphors import extract_metaphor_candidates, parse_candidate_response
from agent_gatsby.llm_client import LLMResponseValidationError
from agent_gatsby.schemas import PassageIndex, PassageRecord


def write_extraction_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "artifacts/manifests").mkdir(parents=True)
    (repo_root / "config/prompts/extractor.md").write_text("Output JSON only.\n", encoding="utf-8")

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
  extractor_prompt_path: "config/prompts/extractor.md"
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
  remove_empty_paragraphs: true
  passage_id_format: "{chapter}.{paragraph}"
extraction:
  output_path: "artifacts/evidence/metaphor_candidates.json"
  raw_debug_output_path: "artifacts/evidence/metaphor_candidates_raw.txt"
  minimum_candidate_count: 1
  maximum_candidate_count: 25
  llm_transport: "ollama_native_chat"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_extract_metaphor_candidates_writes_candidate_file(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_extraction_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return json.dumps(
            [
                {
                    "candidate_id": "C777",
                    "label": "green light",
                    "passage_id": "1.1",
                    "quote": "green light",
                    "rationale": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                    "confidence": 0.91,
                }
            ]
        )

    monkeypatch.setattr("agent_gatsby.extract_metaphors.invoke_text_completion", fake_invoke_text_completion)

    candidates = extract_metaphor_candidates(config)

    output_path = repo_root / "artifacts/evidence/metaphor_candidates.json"
    assert output_path.exists()
    assert len(candidates) == 1
    assert candidates[0].candidate_id == "C001"
    output_text = output_path.read_text(encoding="utf-8")
    assert '"passage_id": "1.1"' in output_text
    assert '"quote": "green light"' in output_text
    assert '"confidence": 0.91' in output_text


def test_extract_metaphor_candidates_saves_raw_output_and_retries_once(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_extraction_repo(repo_root))
    calls = {"count": 0}

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise LLMResponseValidationError("Expected extraction response to be a JSON array", "not json at all")
        return json.dumps(
            [
                {
                    "candidate_id": "C778",
                    "label": "green light",
                    "passage_id": "1.1",
                    "quote": "green light",
                    "rationale": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                    "confidence": 0.92,
                }
            ]
        )

    monkeypatch.setattr("agent_gatsby.extract_metaphors.invoke_text_completion", fake_invoke_text_completion)

    candidates = extract_metaphor_candidates(config)

    debug_path = repo_root / "artifacts/evidence/metaphor_candidates_raw.txt"
    assert len(candidates) == 1
    assert calls["count"] == 2
    assert debug_path.exists()
    assert "not json at all" in debug_path.read_text(encoding="utf-8")


def test_extract_metaphor_candidates_uses_configured_transport_override(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_extraction_repo(repo_root))
    seen_transport_overrides: list[str | None] = []

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        seen_transport_overrides.append(kwargs.get("transport_override"))
        return json.dumps(
            [
                {
                    "candidate_id": "C779",
                    "label": "green light",
                    "passage_id": "1.1",
                    "quote": "green light",
                    "rationale": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                    "confidence": 0.93,
                }
            ]
        )

    monkeypatch.setattr("agent_gatsby.extract_metaphors.invoke_text_completion", fake_invoke_text_completion)

    candidates = extract_metaphor_candidates(config)

    assert len(candidates) == 1
    assert seen_transport_overrides == ["ollama_native_chat"]


def test_parse_candidate_response_repairs_common_live_model_key_typos() -> None:
    response_text = json.dumps(
        [
            {
                "candidate_im": "C001",
                "label": "green light",
                "passage_id": "1.1",
                "quote": "green light",
                "rationale": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                "confidence": 0.95,
            },
            {
                "canidate_id": "C002",
                "label": "dark promise",
                "passage_id": "1.2",
                "quote": "dark promise",
                "ratione": "A metaphor-adjacent image that frames desire as both alluring and ominous.",
                "confidence": 0.81,
            },
        ]
    )

    candidates = parse_candidate_response(response_text)

    assert len(candidates) == 2
    assert candidates[0].candidate_id == "C001"
    assert candidates[1].candidate_id == "C002"
    assert candidates[1].rationale.startswith("A metaphor-adjacent image")


def test_parse_candidate_response_handles_wrapped_candidate_list_objects() -> None:
    response_text = json.dumps(
        {
            "candidates": [
                {
                    "label": "green light",
                    "passage_id": "1.1",
                    "quote_span": "green light",
                    "notes": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                    "confidence": 0.91,
                }
            ]
        }
    )

    candidates = parse_candidate_response(response_text)

    assert len(candidates) == 1
    assert candidates[0].candidate_id == "RAW001"
    assert candidates[0].quote == "green light"
    assert candidates[0].rationale.startswith("A recurring image")
