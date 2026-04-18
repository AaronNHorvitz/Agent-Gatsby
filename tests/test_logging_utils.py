from __future__ import annotations

import logging
from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.logging_utils import build_log_formatter, configure_logging


def write_logging_config(repo_root: Path, *, log_to_file: bool, log_to_console: bool) -> Path:
    (repo_root / "config").mkdir(parents=True)
    config_text = f"""
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
logging:
  level: "INFO"
  log_to_console: {"true" if log_to_console else "false"}
  log_to_file: {"true" if log_to_file else "false"}
  file_path: "artifacts/logs/test_pipeline.log"
  include_timestamps: false
  include_stage_names: false
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_build_log_formatter_respects_timestamp_and_stage_flags(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_logging_config(repo_root, log_to_file=False, log_to_console=False))

    formatter = build_log_formatter(config)

    assert formatter._fmt == "%(levelname)s | %(message)s"


def test_configure_logging_writes_log_file(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_logging_config(repo_root, log_to_file=True, log_to_console=False))

    configure_logging(config)
    logger = logging.getLogger("agent_gatsby.test_logging")
    logger.info("log message from test")

    for handler in logging.getLogger().handlers:
        if hasattr(handler, "flush"):
            handler.flush()

    log_path = repo_root / "artifacts/logs/test_pipeline.log"
    log_text = log_path.read_text(encoding="utf-8")

    assert log_path.exists()
    assert "INFO | log message from test" in log_text

    for handler in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(handler)
        handler.close()
