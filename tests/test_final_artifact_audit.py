from __future__ import annotations

import json
from pathlib import Path

from agent_gatsby.config import load_config
from agent_gatsby.final_artifact_audit import (
    build_pdf_audit_report,
    llm_forensic_audit_report_path,
    pdf_audit_reports_are_renderable,
    run_llm_forensic_audit,
)


def test_build_pdf_audit_report_flags_spanish_contamination() -> None:
    report = build_pdf_audit_report(
        language="spanish",
        pdf_path=Path("spanish.pdf"),
        extracted_text=(
            'la luna prematura AGCIT себя [10] y como si la casa hubiera guiñado un$\\\\un ojo [12]. '
            'juegos nerviosos y esporádíamos [15]. '
            'Please provide the Spanish markdown fragment you would like me to revise. '
            'I am ready to apply the professional academic copyediting standards described in your instructions.'
        ),
    )

    assert report["status"] == "failed"
    assert report["internal_token_issue_count"] >= 1
    assert report["foreign_script_issue_count"] >= 1
    assert report["escape_sequence_issue_count"] >= 1
    assert report["known_bad_token_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1
    assert report["prompt_leak_issue_count"] >= 1


def test_build_pdf_audit_report_flags_english_known_regressions() -> None:
    report = build_pdf_audit_report(
        language="english",
        pdf_path=Path("english.pdf"),
        extracted_text=(
            "Nick Carrawical said the Valley of West was there, Gatsby tried to maintain a punctiliously manner, "
            "He does not use metaphor merely as a decorative layer, and his grotesleque conceits drift into literal and figurative heat "
            "near the outward edge of the universe [2] while Nick remarks, Your place looks like the Es World’s Fair [18]. "
            'They still look out over the solemn dumping ground [5].'
        ),
        page_count=14,
        min_page_count=10,
        max_page_count=13,
    )

    assert report["status"] == "failed"
    assert report["known_bad_token_count"] >= 2
    assert report["page_count_issue_count"] == 1
    assert report["unquoted_quote_reuse_count"] >= 1


def test_build_pdf_audit_report_flags_mandarin_punctuation_bleed() -> None:
    report = build_pdf_audit_report(
        language="mandarin",
        pdf_path=Path("mandarin.pdf"),
        extracted_text="这构成了听觉意象……………… [30]",
    )

    assert report["status"] == "failed"
    assert report["repeated_ellipsis_issue_count"] >= 1
    assert report["citation_neighborhood_issue_count"] >= 1


def test_build_pdf_audit_report_flags_markdown_leak_and_unlocalized_bibliography() -> None:
    report = build_pdf_audit_report(
        language="mandarin",
        pdf_path=Path("mandarin.pdf"),
        extracted_text='### # 梦想的瓦解\n\n1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1, cited passage beginning "hello".\n',
    )

    assert report["status"] == "failed"
    assert report["markdown_heading_leak_count"] >= 1
    assert report["bibliography_localization_issue_count"] >= 1


def test_build_pdf_audit_report_flags_zero_width_characters() -> None:
    report = build_pdf_audit_report(
        language="english",
        pdf_path=Path("english.pdf"),
        extracted_text="Gatsby reaches for the light [1]\u2060.",
    )

    assert report["status"] == "failed"
    assert report["zero_width_issue_count"] >= 1


def test_pdf_audit_reports_are_renderable_requires_all_reports_to_pass() -> None:
    reports = {
        "english": {"status": "passed"},
        "spanish": {"status": "failed"},
        "mandarin": {"status": "passed"},
    }

    assert pdf_audit_reports_are_renderable(reports) is False


def write_forensic_audit_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "config/prompts/final_forensic_audit.md").write_text("Return JSON only.\n", encoding="utf-8")
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
prompts:
  final_forensic_audit_prompt_path: "config/prompts/final_forensic_audit.md"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
  llm_forensic_audit_enabled: true
models:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"
  primary_reasoner: "gemma4:26b"
  final_critic: "gemma4:26b"
pdf:
  english_pdf_path: "outputs/Gatsby_Analysis_English.pdf"
  spanish_pdf_path: "outputs/Gatsby_Analysis_Spanish.pdf"
  mandarin_pdf_path: "outputs/Gatsby_Analysis_Mandarin.pdf"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_run_llm_forensic_audit_writes_advisory_report(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_forensic_audit_repo(repo_root))

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        return json.dumps(
            {
                "defects": [
                    {
                        "language": "spanish",
                        "original_text": "Please provide the Spanish markdown fragment you would like me to revise.",
                        "proposed_correction": "Remove the leaked assistant sentence.",
                        "severity": "High",
                        "category": "system_leak",
                    }
                ],
                "notes": "Found one high-severity prompt leak.",
            }
        )

    monkeypatch.setattr(
        "agent_gatsby.final_artifact_audit.invoke_text_completion",
        fake_invoke_text_completion,
    )

    report = run_llm_forensic_audit(
        config,
        language="spanish",
        pdf_path=Path("outputs/Gatsby_Analysis_Spanish.pdf"),
        extracted_text="Please provide the Spanish markdown fragment you would like me to revise.",
        page_count=13,
    )

    saved = json.loads(llm_forensic_audit_report_path(config, "spanish").read_text(encoding="utf-8"))
    assert report["status"] == "defects_found"
    assert report["defect_count"] == 1
    assert saved["defects"][0]["severity"] == "High"
    assert saved["defects"][0]["category"] == "system_leak"
