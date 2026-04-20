from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_gatsby.config import load_config
from agent_gatsby.orchestrator import main, stage_render_pdfs


def write_test_repo(repo_root: Path) -> Path:
    (repo_root / "config/prompts").mkdir(parents=True)
    (repo_root / "data/source").mkdir(parents=True)
    (repo_root / "config/prompts/extractor.md").write_text("Output JSON only.\n", encoding="utf-8")
    (repo_root / "config/prompts/outline.md").write_text("Output JSON only.\n", encoding="utf-8")
    (repo_root / "config/prompts/draft.md").write_text("Output markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/critic.md").write_text("Output revised markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_es.md").write_text("Output translated markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_es_cleanup.md").write_text("Output cleaned Spanish markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh.md").write_text("Output translated markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/translator_zh_cleanup.md").write_text("Output cleaned Chinese markdown only.\n", encoding="utf-8")
    (repo_root / "config/prompts/translation_qa.md").write_text("Output JSON only.\n", encoding="utf-8")

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
models:
  endpoint: "http://localhost:11434/v1"
  api_key: "ollama"
  primary_reasoner: "gemma4:26b"
  translator_es: "gemma4:26b"
  translator_zh: "gemma4:26b"
  timeout_seconds: 1
  max_retries: 0
  retry_backoff_seconds: 0
llm_defaults:
  temperature: 0.2
  top_p: 0.9
  max_tokens: 512
prompts:
  extractor_prompt_path: "config/prompts/extractor.md"
  outline_prompt_path: "config/prompts/outline.md"
  draft_prompt_path: "config/prompts/draft.md"
  critic_prompt_path: "config/prompts/critic.md"
  translator_es_prompt_path: "config/prompts/translator_es.md"
  translator_es_cleanup_prompt_path: "config/prompts/translator_es_cleanup.md"
  translator_zh_prompt_path: "config/prompts/translator_zh.md"
  translator_zh_cleanup_prompt_path: "config/prompts/translator_zh_cleanup.md"
  qa_prompt_path: "config/prompts/translation_qa.md"
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
  require_exact_quote_match: true
  reject_missing_passage_ids: true
  reject_empty_rationales: true
  minimum_quote_length: 8
  status_for_verified_entries: "verified"
outline:
  output_path: "artifacts/drafts/outline.json"
  minimum_section_count: 1
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
  display_citation_format: "[{citation_number}]"
  citation_appendix_heading: "Citations"
  citation_text_title: "Citation Text"
  citation_text_output_path: "artifacts/final/citation_text.md"
  context_window_paragraphs_before: 1
  context_window_paragraphs_after: 1
  write_section_by_section: true
  max_evidence_per_section: 4
  citation_format: "[{passage_id}]"
  preserve_direct_quotes: true
  forbid_invented_citations: true
  forbid_invented_quotes: true
  target_tone: "formal academic literary analysis"
verification:
  output_path: "artifacts/qa/english_verification_report.json"
  citation_registry_output_path: "artifacts/qa/citation_registry.json"
  fail_on_quote_mismatch: true
  fail_on_invalid_citation: true
  normalize_curly_quotes_for_matching: true
  require_all_citations_to_resolve: true
translation:
  max_chunk_chars: 5000
  post_edit_body: true
translation_outputs:
  spanish_output_path: "artifacts/translations/analysis_spanish_draft.md"
  mandarin_output_path: "artifacts/translations/analysis_mandarin_draft.md"
  spanish_qa_report_path: "artifacts/qa/spanish_qa_report.json"
  mandarin_qa_report_path: "artifacts/qa/mandarin_qa_report.json"
pdf:
  english_pdf_path: "outputs/Gatsby_Analysis_English.pdf"
  spanish_pdf_path: "outputs/Gatsby_Analysis_Spanish.pdf"
  mandarin_pdf_path: "outputs/Gatsby_Analysis_Mandarin.pdf"
  english_font_regular: "NotoSerif-Regular.ttf"
  english_font_bold: "NotoSerif-Bold.ttf"
  spanish_font_regular: "NotoSerif-Regular.ttf"
  spanish_font_bold: "NotoSerif-Bold.ttf"
  mandarin_font_regular: "NotoSansCJK-VF.ttc"
manifest:
  output_path: "outputs/final_manifest.json"
orchestration:
  supported_stages:
    - "ingest"
    - "normalize"
    - "index"
    - "extract_metaphors"
    - "build_evidence_ledger"
    - "plan_outline"
    - "draft_english"
    - "verify_english"
    - "critique_english"
    - "freeze_english"
    - "translate_spanish"
    - "qa_spanish"
    - "translate_mandarin"
    - "qa_mandarin"
    - "render_pdfs"
    - "write_manifest"
"""
    config_path = repo_root / "config/config.yaml"
    config_path.write_text(config_text.strip() + "\n", encoding="utf-8")
    return config_path


def test_orchestrator_runs_all_stages_and_writes_artifacts(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config_path = write_test_repo(repo_root)

    def fake_invoke_text_completion(*args, **kwargs) -> str:
        stage_name = kwargs.get("stage_name")
        if stage_name == "plan_outline":
            return json.dumps(
                {
                    "title": "Metaphor and Desire in Gatsby",
                    "thesis": "Fitzgerald turns desire into distance through recurring metaphor.",
                    "intro_notes": "Frame metaphor as a structural device.",
                    "sections": [
                        {
                            "section_id": "S1",
                            "heading": "The Green Light",
                            "evidence_ids": ["E001"],
                        }
                    ],
                    "conclusion_notes": "Return to the collapse of idealized longing.",
                }
            )
        if stage_name == "draft_english":
            user_prompt = kwargs.get("user_prompt", "")
            if "Section type: introduction" in user_prompt:
                return "Nick's opening perspective frames metaphor as the language through which aspiration becomes socially visible."
            if "Section type: conclusion" in user_prompt:
                return 'The novel closes by showing how the "green light" remains a durable sign of desire even as it recedes [1.1].'
            return 'Gatsby\'s "green light" turns desire into a visible performance of longing [1.1].'
        if stage_name == "critique_english":
            return "\n".join(
                [
                    "# Metaphor and Desire in Gatsby",
                    "",
                    "## Introduction",
                    "",
                    'Nick\'s opening perspective frames metaphor as the language through which aspiration becomes socially visible through the "green light" [1.1].',
                    "",
                    "## The Green Light",
                    "",
                    'Gatsby\'s "green light" turns desire into a visible performance of longing while sharpening the section\'s analytical focus [1.1].',
                    "",
                    "## Conclusion",
                    "",
                    'The novel closes by showing how the "green light" remains a durable sign of desire even as it recedes [1.1].',
                ]
            )
        if stage_name in {"translate_spanish", "translate_mandarin", "translate_spanish_cleanup", "translate_mandarin_cleanup"}:
            user_prompt = kwargs.get("user_prompt", "")
            if "English markdown chunk:\n\n" in user_prompt:
                return user_prompt.split("English markdown chunk:\n\n", maxsplit=1)[1]
            if "Existing translated markdown chunk:\n\n" in user_prompt:
                return user_prompt.split("Existing translated markdown chunk:\n\n", maxsplit=1)[1]
            return user_prompt.split("Existing translated markdown fragment:\n\n", maxsplit=1)[1]
        return json.dumps(
            [
                {
                    "candidate_id": "C999",
                    "label": "green light",
                    "passage_id": "1.1",
                    "quote": "green light",
                    "rationale": "A recurring image that turns Gatsby's longing into a visible object of desire.",
                    "confidence": 0.94,
                }
            ]
        )

    monkeypatch.setattr("agent_gatsby.extract_metaphors.invoke_text_completion", fake_invoke_text_completion)
    monkeypatch.setattr("agent_gatsby.plan_outline.invoke_text_completion", fake_invoke_text_completion)
    monkeypatch.setattr("agent_gatsby.draft_english.invoke_text_completion", fake_invoke_text_completion)
    monkeypatch.setattr("agent_gatsby.critique_and_edit.invoke_text_completion", fake_invoke_text_completion)
    monkeypatch.setattr("agent_gatsby.translation_common.invoke_text_completion", fake_invoke_text_completion)

    def fake_render_pdfs(config):
        for path in (
            config.english_pdf_output_path,
            config.spanish_pdf_output_path,
            config.mandarin_pdf_output_path,
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pdf\n", encoding="utf-8")
        return [
            config.english_pdf_output_path,
            config.spanish_pdf_output_path,
            config.mandarin_pdf_output_path,
        ]

    def fake_write_manifest(config):
        payload = {"output_files": [str(config.english_pdf_output_path)]}
        config.final_manifest_output_path.parent.mkdir(parents=True, exist_ok=True)
        config.final_manifest_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def fake_audit_rendered_pdfs(config):
        reports = {
            "english": {"status": "passed"},
            "spanish": {"status": "passed"},
            "mandarin": {"status": "passed"},
        }
        for language in reports:
            path = repo_root / f"artifacts/qa/{language}_pdf_audit_report.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(reports[language]), encoding="utf-8")
        return reports

    monkeypatch.setattr("agent_gatsby.orchestrator.render_pdfs", fake_render_pdfs)
    monkeypatch.setattr("agent_gatsby.orchestrator.audit_rendered_pdfs", fake_audit_rendered_pdfs)
    monkeypatch.setattr("agent_gatsby.orchestrator.write_manifest", fake_write_manifest)
    exit_code = main(["--config", str(config_path), "--run", "all"])

    assert exit_code == 0
    assert (repo_root / "artifacts/manifests/source_manifest.json").exists()
    assert (repo_root / "data/normalized/gatsby_locked.txt").exists()
    assert (repo_root / "artifacts/manifests/passage_index.json").exists()
    assert (repo_root / "artifacts/evidence/metaphor_candidates.json").exists()
    assert (repo_root / "artifacts/evidence/evidence_ledger.json").exists()
    assert (repo_root / "artifacts/drafts/outline.json").exists()
    assert (repo_root / "artifacts/drafts/analysis_english_draft.md").exists()
    assert (repo_root / "artifacts/qa/english_draft_timing.json").exists()
    assert (repo_root / "artifacts/qa/english_verification_report.json").exists()
    assert (repo_root / "artifacts/drafts/analysis_english_final.md").exists()
    assert (repo_root / "artifacts/final/analysis_english_master.md").exists()
    final_text = (repo_root / "artifacts/drafts/analysis_english_final.md").read_text(encoding="utf-8")
    assert "[1]" in final_text
    assert "## Citations" in final_text
    assert '1. F. Scott Fitzgerald, *The Great Gatsby*, ch. 1, para. 1' in final_text
    assert (repo_root / "artifacts/final/citation_text.md").exists()
    assert (repo_root / "artifacts/qa/citation_registry.json").exists()
    assert (repo_root / "artifacts/translations/analysis_spanish_draft.md").exists()
    assert (repo_root / "artifacts/translations/analysis_mandarin_draft.md").exists()
    assert (repo_root / "artifacts/qa/spanish_qa_report.json").exists()
    assert (repo_root / "artifacts/qa/mandarin_qa_report.json").exists()
    assert (repo_root / "outputs/Gatsby_Analysis_English.pdf").exists()
    assert (repo_root / "outputs/Gatsby_Analysis_Spanish.pdf").exists()
    assert (repo_root / "outputs/Gatsby_Analysis_Mandarin.pdf").exists()
    assert (repo_root / "outputs/final_manifest.json").exists()

    log_text = (repo_root / "artifacts/logs/pipeline.log").read_text(encoding="utf-8")
    assert "Starting stage: ingest" in log_text
    assert "Finished stage: write_manifest (" in log_text
    assert "Total pipeline time:" in log_text


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


def test_stage_render_pdfs_requires_structurally_renderable_translation_reports(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_test_repo(repo_root))
    render_called = False

    def fake_stage_qa_spanish(config, context):
        context["spanish_qa_report"] = {
            "non_empty_translation": True,
            "heading_count_match": True,
            "section_order_match": True,
            "citation_count_match": True,
            "quote_marker_count_match": True,
            "citations_section_present": True,
            "english_citation_entry_count": 1,
            "translated_citation_entry_count": 0,
            "citation_entry_count_match": False,
            "citations_heading_without_entries": True,
        }

    def fake_stage_qa_mandarin(config, context):
        context["mandarin_qa_report"] = {
            "non_empty_translation": True,
            "heading_count_match": True,
            "section_order_match": True,
            "citation_count_match": True,
            "quote_marker_count_match": True,
            "citations_section_present": True,
            "english_citation_entry_count": 1,
            "translated_citation_entry_count": 1,
            "citation_entry_count_match": True,
            "citations_heading_without_entries": False,
        }

    def fake_render_pdfs(config):
        nonlocal render_called
        render_called = True
        return []

    def fake_audit_rendered_pdfs(config):
        return {
            "english": {"status": "passed"},
            "spanish": {"status": "passed"},
            "mandarin": {"status": "passed"},
        }

    monkeypatch.setattr("agent_gatsby.orchestrator.stage_qa_spanish", fake_stage_qa_spanish)
    monkeypatch.setattr("agent_gatsby.orchestrator.stage_qa_mandarin", fake_stage_qa_mandarin)
    monkeypatch.setattr("agent_gatsby.orchestrator.render_pdfs", fake_render_pdfs)
    monkeypatch.setattr("agent_gatsby.orchestrator.audit_rendered_pdfs", fake_audit_rendered_pdfs)

    with pytest.raises(ValueError, match="Spanish translation failed required structural QA"):
        stage_render_pdfs(
            config,
            {
                "english_master": "# Title\n",
                "spanish_translation": "# Titulo\n",
                "mandarin_translation": "# 标题\n",
            },
        )

    assert render_called is False


def test_stage_render_pdfs_requires_passing_pdf_audit(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    config = load_config(write_test_repo(repo_root))
    render_called = False

    def fake_stage_qa_spanish(config, context):
        context["spanish_qa_report"] = {
            "non_empty_translation": True,
            "heading_count_match": True,
            "section_order_match": True,
            "citation_count_match": True,
            "quote_marker_count_match": True,
            "citations_section_present": True,
            "english_citation_entry_count": 1,
            "translated_citation_entry_count": 1,
            "citation_entry_count_match": True,
            "citations_heading_without_entries": False,
            "untranslated_body_quote_count": 0,
            "citation_glue_issue_count": 0,
            "internal_token_issue_count": 0,
            "escape_sequence_issue_count": 0,
            "foreign_script_issue_count": 0,
            "repeated_ellipsis_issue_count": 0,
            "known_bad_token_count": 0,
            "citation_neighborhood_issue_count": 0,
            "mixed_script_issue_count": 0,
            "forbidden_mandarin_variant_count": 0,
        }

    def fake_stage_qa_mandarin(config, context):
        context["mandarin_qa_report"] = {
            "non_empty_translation": True,
            "heading_count_match": True,
            "section_order_match": True,
            "citation_count_match": True,
            "quote_marker_count_match": True,
            "citations_section_present": True,
            "english_citation_entry_count": 1,
            "translated_citation_entry_count": 1,
            "citation_entry_count_match": True,
            "citations_heading_without_entries": False,
            "untranslated_body_quote_count": 0,
            "citation_glue_issue_count": 0,
            "internal_token_issue_count": 0,
            "escape_sequence_issue_count": 0,
            "foreign_script_issue_count": 0,
            "repeated_ellipsis_issue_count": 0,
            "known_bad_token_count": 0,
            "citation_neighborhood_issue_count": 0,
            "mixed_script_issue_count": 0,
            "forbidden_mandarin_variant_count": 0,
        }

    def fake_render_pdfs(config):
        nonlocal render_called
        render_called = True
        return []

    def fake_audit_rendered_pdfs(config):
        return {
            "english": {"status": "passed"},
            "spanish": {"status": "failed"},
            "mandarin": {"status": "passed"},
        }

    monkeypatch.setattr("agent_gatsby.orchestrator.stage_qa_spanish", fake_stage_qa_spanish)
    monkeypatch.setattr("agent_gatsby.orchestrator.stage_qa_mandarin", fake_stage_qa_mandarin)
    monkeypatch.setattr("agent_gatsby.orchestrator.render_pdfs", fake_render_pdfs)
    monkeypatch.setattr("agent_gatsby.orchestrator.audit_rendered_pdfs", fake_audit_rendered_pdfs)

    with pytest.raises(ValueError, match="final artifact audit failed"):
        stage_render_pdfs(
            config,
            {
                "english_master": "# Title\n",
                "spanish_translation": "# Titulo\n",
                "mandarin_translation": "# 标题\n",
            },
        )

    assert render_called is True
