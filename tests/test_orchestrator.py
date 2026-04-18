from __future__ import annotations

from pathlib import Path

from agent_gatsby.orchestrator import main


def write_test_repo(repo_root: Path) -> Path:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "data/source").mkdir(parents=True)

    source_text = (
        "\ufeffThe Project Gutenberg eBook of The Great Gatsby\n\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK THE GREAT GATSBY ***\n\n"
        "I\n\n"
        "Gatsby reached toward the green light at the end of the dock.\n\n"
        "The water between him and the light looked like a dark promise.\n\n"
        "II\n\n"
        "The valley of ashes lay under the gray morning like a ruined field.\n\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK THE GREAT GATSBY ***\n"
    )
    (repo_root / "data/source/gatsby_source.txt").write_text(source_text, encoding="utf-8")

    config_text = """
project:
  name: "Agent Gatsby"
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
logging:
  level: "INFO"
  log_to_console: false
  log_to_file: true
  file_path: "artifacts/logs/pipeline.log"
  include_timestamps: false
  include_stage_names: true
indexing:
  output_path: "artifacts/manifests/passage_index.json"
  chapter_pattern: "^Chapter\\\\s+[IVXLC0-9]+$"
  paragraph_split_strategy: "blank_line"
  remove_empty_paragraphs: true
  passage_id_format: "{chapter}.{paragraph}"
orchestration:
  supported_stages:
    - "ingest"
    - "normalize"
    - "index"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_orchestrator_runs_all_stages_and_writes_artifacts(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config_path = write_test_repo(repo_root)

    exit_code = main(["--config", str(config_path), "--run", "all"])

    assert exit_code == 0
    assert (repo_root / "artifacts/manifests/source_manifest.json").exists()
    assert (repo_root / "data/normalized/gatsby_locked.txt").exists()
    assert (repo_root / "artifacts/manifests/passage_index.json").exists()

    log_text = (repo_root / "artifacts/logs/pipeline.log").read_text(encoding="utf-8")
    assert "Starting stage: ingest" in log_text
    assert "Finished stage: index" in log_text


def test_orchestrator_single_stage_run_builds_upstream_artifacts(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config_path = write_test_repo(repo_root)

    exit_code = main(["--config", str(config_path), "--run", "index"])

    assert exit_code == 0
    assert (repo_root / "artifacts/manifests/source_manifest.json").exists()
    assert (repo_root / "data/normalized/gatsby_locked.txt").exists()
    passage_index_path = repo_root / "artifacts/manifests/passage_index.json"
    assert passage_index_path.exists()
    assert '"passage_id": "2.1"' in passage_index_path.read_text(encoding="utf-8")
