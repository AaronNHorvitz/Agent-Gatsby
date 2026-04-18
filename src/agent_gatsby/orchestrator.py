"""
Minimal CLI orchestrator for the early Agent Gatsby pipeline stages.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from typing import Any

from agent_gatsby.build_evidence_ledger import build_evidence_ledger
from agent_gatsby.config import AppConfig, load_config
from agent_gatsby.data_ingest import ingest_source
from agent_gatsby.draft_english import draft_english
from agent_gatsby.extract_metaphors import extract_metaphor_candidates
from agent_gatsby.index_text import index_normalized_text
from agent_gatsby.logging_utils import configure_logging
from agent_gatsby.normalize import normalize_source
from agent_gatsby.plan_outline import plan_outline
from agent_gatsby.verify_citations import verify_english_draft

LOGGER = logging.getLogger(__name__)

StageContext = dict[str, Any]
StageHandler = Callable[[AppConfig, StageContext], None]
IMPLEMENTED_STAGE_ORDER = (
    "ingest",
    "normalize",
    "index",
    "extract_metaphors",
    "build_evidence_ledger",
    "plan_outline",
    "draft_english",
    "verify_english",
)


def stage_ingest(config: AppConfig, context: StageContext) -> None:
    source_text, source_manifest = ingest_source(config)
    context["source_text"] = source_text
    context["source_manifest"] = source_manifest


def stage_normalize(config: AppConfig, context: StageContext) -> None:
    if "source_text" not in context:
        stage_ingest(config, context)

    context["normalized_text"] = normalize_source(config, context["source_text"])


def stage_index(config: AppConfig, context: StageContext) -> None:
    if "normalized_text" not in context:
        stage_normalize(config, context)

    context["passage_index"] = index_normalized_text(config, context["normalized_text"])


def stage_extract_metaphors(config: AppConfig, context: StageContext) -> None:
    if "passage_index" not in context:
        stage_index(config, context)

    context["candidates"] = extract_metaphor_candidates(config, context["passage_index"])


def stage_build_evidence_ledger(config: AppConfig, context: StageContext) -> None:
    if "candidates" not in context:
        stage_extract_metaphors(config, context)
    if "passage_index" not in context:
        stage_index(config, context)

    evidence_records, rejected_candidates = build_evidence_ledger(
        config,
        candidates=context["candidates"],
        passage_index=context["passage_index"],
    )
    context["evidence_records"] = evidence_records
    context["rejected_candidates"] = rejected_candidates


def stage_plan_outline(config: AppConfig, context: StageContext) -> None:
    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)

    context["outline"] = plan_outline(config, evidence_records=context["evidence_records"])


def stage_draft_english(config: AppConfig, context: StageContext) -> None:
    if "outline" not in context:
        stage_plan_outline(config, context)
    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)

    context["english_draft"] = draft_english(
        config,
        outline=context["outline"],
        evidence_records=context["evidence_records"],
    )


def stage_verify_english(config: AppConfig, context: StageContext) -> None:
    if "english_draft" not in context:
        stage_draft_english(config, context)
    if "passage_index" not in context:
        stage_index(config, context)
    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)

    context["english_verification_report"] = verify_english_draft(
        config,
        draft_text=context["english_draft"],
        evidence_records=context["evidence_records"],
        passage_index=context["passage_index"],
    )


def get_stage_registry() -> dict[str, StageHandler]:
    return {
        "ingest": stage_ingest,
        "normalize": stage_normalize,
        "index": stage_index,
        "extract_metaphors": stage_extract_metaphors,
        "build_evidence_ledger": stage_build_evidence_ledger,
        "plan_outline": stage_plan_outline,
        "draft_english": stage_draft_english,
        "verify_english": stage_verify_english,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Agent Gatsby pipeline stages")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to the YAML config file",
    )
    parser.add_argument(
        "--run",
        default="all",
        help="Stage to run or 'all'",
    )
    return parser


def resolve_stage_sequence(requested_stage: str, config: AppConfig) -> list[str]:
    registry = get_stage_registry()
    configured_stages = set(config.orchestration.get("supported_stages", []))

    if requested_stage == "all":
        return list(IMPLEMENTED_STAGE_ORDER)

    if configured_stages and requested_stage not in configured_stages:
        supported = ", ".join(["all", *sorted(configured_stages)])
        raise ValueError(f"Unknown stage '{requested_stage}'. Supported values: {supported}")

    if requested_stage not in registry:
        raise NotImplementedError(
            f"Stage '{requested_stage}' is defined but not implemented yet. "
            f"Implemented stages: {', '.join(IMPLEMENTED_STAGE_ORDER)}"
        )

    return [requested_stage]


def run_stage(stage_name: str, config: AppConfig, context: StageContext) -> None:
    registry = get_stage_registry()
    LOGGER.info("Starting stage: %s", stage_name)
    registry[stage_name](config, context)
    LOGGER.info("Finished stage: %s", stage_name)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        configure_logging(config)
        stages = resolve_stage_sequence(args.run, config)

        context: StageContext = {}
        for stage_name in stages:
            run_stage(stage_name, config, context)

        LOGGER.info("Completed requested pipeline stages: %s", ", ".join(stages))
        return 0
    except Exception as exc:
        if logging.getLogger().handlers:
            LOGGER.exception("Pipeline execution failed: %s", exc)
        else:
            parser.exit(status=1, message=f"Pipeline execution failed: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
