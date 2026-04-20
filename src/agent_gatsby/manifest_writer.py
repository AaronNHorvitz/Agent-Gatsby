"""
Final manifest writer for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.final_artifact_audit import pdf_audit_report_paths
from agent_gatsby.schemas import FinalManifest
from agent_gatsby.translation_common import english_master_regression_report_path

LOGGER = logging.getLogger(__name__)


def existing_paths(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def load_source_hash(config: AppConfig) -> str | None:
    path = config.source_manifest_path
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("sha256")


def build_final_manifest(config: AppConfig) -> FinalManifest:
    output_files = existing_paths(
        [
            config.english_master_output_path,
            config.final_draft_output_path,
            config.citation_text_output_path,
            config.spanish_translation_output_path,
            config.mandarin_translation_output_path,
            config.english_pdf_output_path,
            config.spanish_pdf_output_path,
            config.mandarin_pdf_output_path,
        ]
    )
    qa_reports = existing_paths(
        [
            config.english_verification_report_path,
            english_master_regression_report_path(config),
            config.spanish_qa_report_path,
            config.mandarin_qa_report_path,
            config.citation_registry_output_path,
            *pdf_audit_report_paths(config),
        ]
    )
    models = {
        "primary_reasoner": str(config.models.get("primary_reasoner", "")),
        "final_critic": str(config.models.get("final_critic", "")),
        "translator_es": str(config.models.get("translator_es", "")),
        "translator_zh": str(config.models.get("translator_zh", "")),
    }
    return FinalManifest(
        generated_at=utc_now_iso(),
        source_hash=load_source_hash(config),
        config_path=str(config.config_path),
        output_files=output_files,
        qa_reports=qa_reports,
        models=models,
    )


def write_manifest(config: AppConfig) -> FinalManifest:
    manifest = build_final_manifest(config)
    output_path = config.final_manifest_output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote final manifest to %s", output_path)
    return manifest
