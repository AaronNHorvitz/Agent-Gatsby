from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.llm_client import extract_message_text, invoke_text_completion


def write_llm_config(repo_root: Path) -> Path:
    (repo_root / "config").mkdir(parents=True)
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
  timeout_seconds: 1
  max_retries: 1
  retry_backoff_seconds: 0
llm_defaults:
  temperature: 0.2
  top_p: 0.9
  max_tokens: 256
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def fake_response(content, *, reasoning=None, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, reasoning=reasoning),
                finish_reason=finish_reason,
            )
        ]
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        next_response = self.responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


def test_extract_message_text_joins_structured_chunks() -> None:
    response = fake_response(
        [
            {"text": "Hello "},
            SimpleNamespace(text="world"),
            {"ignored": True},
        ]
    )

    assert extract_message_text(response) == "Hello world"


def test_invoke_text_completion_retries_empty_content_and_returns_valid_text(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_llm_config(repo_root))
    fake_client = FakeClient([fake_response(""), fake_response("Verified response")])

    monkeypatch.setattr("agent_gatsby.llm_client.build_client", lambda config: fake_client)
    monkeypatch.setattr("agent_gatsby.llm_client.time.sleep", lambda seconds: None)

    response_text = invoke_text_completion(
        config,
        stage_name="draft_english",
        system_prompt="system",
        user_prompt="user",
        response_validator=lambda text: None,
    )

    assert response_text == "Verified response"
    assert len(fake_client.chat.completions.calls) == 2
    assert fake_client.chat.completions.calls[0]["model"] == "gemma4:26b"


def test_invoke_text_completion_raises_when_validator_rejects_all_attempts(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_llm_config(repo_root))
    fake_client = FakeClient([fake_response("bad"), fake_response("still bad")])

    monkeypatch.setattr("agent_gatsby.llm_client.build_client", lambda config: fake_client)
    monkeypatch.setattr("agent_gatsby.llm_client.time.sleep", lambda seconds: None)

    with pytest.raises(ValueError, match="not acceptable"):
        invoke_text_completion(
            config,
            stage_name="draft_english",
            system_prompt="system",
            user_prompt="user",
            response_validator=lambda text: (_ for _ in ()).throw(ValueError("not acceptable")),
        )


def test_invoke_text_completion_reports_reasoning_diagnostics_for_empty_content(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_llm_config(repo_root))
    fake_client = FakeClient(
        [
            fake_response("", reasoning="internal draft planning", finish_reason="length"),
            fake_response("", reasoning="internal draft planning", finish_reason="length"),
        ]
    )

    monkeypatch.setattr("agent_gatsby.llm_client.build_client", lambda config: fake_client)
    monkeypatch.setattr("agent_gatsby.llm_client.time.sleep", lambda seconds: None)

    with pytest.raises(ValueError, match=r"finish_reason=length, reasoning_len=23"):
        invoke_text_completion(
            config,
            stage_name="draft_english",
            system_prompt="system",
            user_prompt="user",
            response_validator=lambda text: None,
        )
