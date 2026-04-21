"""CLI orchestration for the full Agent Gatsby pipeline.

This module wires the stage-level pipeline functions into a minimal command-line
interface. It preserves explicit stage ordering, supports partial reruns from a
requested stage, and enforces the promotion gates that stop translation, PDF
rendering, and manifest writing when upstream validation fails.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from typing import Any

from agent_gatsby.build_evidence_ledger import build_evidence_ledger
from agent_gatsby.bilingual_qa import qa_mandarin, qa_spanish, translation_report_is_renderable
from agent_gatsby.config import AppConfig, load_config
from agent_gatsby.critique_and_edit import critique_and_edit
from agent_gatsby.data_ingest import ingest_source
from agent_gatsby.draft_english import draft_english
from agent_gatsby.extract_metaphors import extract_metaphor_candidates
from agent_gatsby.final_artifact_audit import (
    audit_rendered_pdfs,
    pdf_audit_report_paths,
    pdf_audit_reports_are_renderable,
)
from agent_gatsby.index_text import index_normalized_text
from agent_gatsby.logging_utils import configure_logging
from agent_gatsby.manifest_writer import write_manifest
from agent_gatsby.normalize import normalize_source
from agent_gatsby.pdf_compiler import render_pdfs
from agent_gatsby.plan_outline import plan_outline
from agent_gatsby.translation_common import freeze_english_master
from agent_gatsby.translate_mandarin import translate_mandarin
from agent_gatsby.translate_spanish import translate_spanish
from agent_gatsby.verify_citations import repair_cited_quote_alignment, verify_english_draft

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
    "critique_english",
    "freeze_english",
    "translate_spanish",
    "qa_spanish",
    "translate_mandarin",
    "qa_mandarin",
    "render_pdfs",
    "write_manifest",
)


def stage_ingest(config: AppConfig, context: StageContext) -> None:
    """Run source ingestion and cache the results in stage context.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with source text and manifest objects.
    """

    source_text, source_manifest = ingest_source(config)
    context["source_text"] = source_text
    context["source_manifest"] = source_manifest


def stage_normalize(config: AppConfig, context: StageContext) -> None:
    """Normalize the locked source text and cache the result.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with normalized text.
    """

    if "source_text" not in context:
        stage_ingest(config, context)

    context["normalized_text"] = normalize_source(config, context["source_text"])


def stage_index(config: AppConfig, context: StageContext) -> None:
    """Build the deterministic passage index for the normalized text.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the passage index.
    """

    if "normalized_text" not in context:
        stage_normalize(config, context)

    context["passage_index"] = index_normalized_text(config, context["normalized_text"])


def stage_extract_metaphors(config: AppConfig, context: StageContext) -> None:
    """Extract candidate metaphor records from the passage index.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with extracted candidates.
    """

    if "passage_index" not in context:
        stage_index(config, context)

    context["candidates"] = extract_metaphor_candidates(config, context["passage_index"])


def stage_build_evidence_ledger(config: AppConfig, context: StageContext) -> None:
    """Promote verified evidence records from extracted candidates.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with evidence and rejection artifacts.
    """

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
    """Generate the structured English outline from verified evidence.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the outline plan.
    """

    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)

    context["outline"] = plan_outline(config, evidence_records=context["evidence_records"])


def stage_draft_english(config: AppConfig, context: StageContext) -> None:
    """Draft the English analysis from the outline and evidence ledger.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the English draft text.
    """

    if "outline" not in context:
        stage_plan_outline(config, context)
    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)
    if "passage_index" not in context:
        stage_index(config, context)

    context["english_draft"] = draft_english(
        config,
        outline=context["outline"],
        evidence_records=context["evidence_records"],
        passage_index=context["passage_index"],
    )


def stage_verify_english(config: AppConfig, context: StageContext) -> None:
    """Repair cited quote drift and verify the English draft.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the English verification report.

    Notes
    -----
    Before verification, the stage applies canonical quote-alignment repairs to
    cited direct quotes so near-miss quote reuse is normalized to the verified
    evidence ledger.
    """

    if "english_draft" not in context:
        stage_draft_english(config, context)
    if "passage_index" not in context:
        stage_index(config, context)
    if "evidence_records" not in context:
        stage_build_evidence_ledger(config, context)

    repaired_draft, quote_repairs = repair_cited_quote_alignment(
        context["english_draft"],
        evidence_records=context["evidence_records"],
        passage_index=context["passage_index"],
        appendix_heading=str(config.drafting.get("citation_appendix_heading", "Citations")),
        normalize_curly_quotes=bool(config.verification.get("normalize_curly_quotes_for_matching", True)),
    )
    if quote_repairs:
        config.draft_output_path.write_text(repaired_draft, encoding="utf-8")
        context["english_draft"] = repaired_draft
        LOGGER.info(
            "Applied %d canonical English quote alignment repairs before verification",
            len(quote_repairs),
        )

    context["english_verification_report"] = verify_english_draft(
        config,
        draft_text=context["english_draft"],
        evidence_records=context["evidence_records"],
        passage_index=context["passage_index"],
    )


def stage_critique_english(config: AppConfig, context: StageContext) -> None:
    """Run the bounded editorial refinement pass on the English draft.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the editorially refined English
        draft or its safe fallback.
    """

    if "english_verification_report" not in context:
        stage_verify_english(config, context)
    if "english_draft" not in context:
        stage_draft_english(config, context)

    context["english_final"] = critique_and_edit(
        config,
        draft_text=context["english_draft"],
    )


def stage_freeze_english(config: AppConfig, context: StageContext) -> None:
    """Freeze the verified English master for downstream translation.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the frozen English master text.
    """

    if "english_final" not in context and not config.final_draft_output_path.exists():
        stage_critique_english(config, context)
    context["english_master"] = freeze_english_master(config)


def stage_translate_spanish(config: AppConfig, context: StageContext) -> None:
    """Translate the frozen English master into Spanish.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the Spanish translation text.
    """

    if "english_master" not in context and not config.english_master_output_path.exists():
        stage_freeze_english(config, context)

    context["spanish_translation"] = translate_spanish(
        config,
        english_master_text=context.get("english_master"),
    )


def stage_qa_spanish(config: AppConfig, context: StageContext) -> None:
    """Run structural QA on the Spanish translation package.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the Spanish QA report.
    """

    if "spanish_translation" not in context and not config.spanish_translation_output_path.exists():
        stage_translate_spanish(config, context)
    if "english_master" not in context and not config.english_master_output_path.exists():
        stage_freeze_english(config, context)

    context["spanish_qa_report"] = qa_spanish(
        config,
        english_master_text=context.get("english_master"),
        translated_text=context.get("spanish_translation"),
    )


def stage_translate_mandarin(config: AppConfig, context: StageContext) -> None:
    """Translate the frozen English master into Simplified Chinese.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the Mandarin translation text.
    """

    if "english_master" not in context and not config.english_master_output_path.exists():
        stage_freeze_english(config, context)

    context["mandarin_translation"] = translate_mandarin(
        config,
        english_master_text=context.get("english_master"),
    )


def stage_qa_mandarin(config: AppConfig, context: StageContext) -> None:
    """Run structural QA on the Mandarin translation package.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the Mandarin QA report.
    """

    if "mandarin_translation" not in context and not config.mandarin_translation_output_path.exists():
        stage_translate_mandarin(config, context)
    if "english_master" not in context and not config.english_master_output_path.exists():
        stage_freeze_english(config, context)

    context["mandarin_qa_report"] = qa_mandarin(
        config,
        english_master_text=context.get("english_master"),
        translated_text=context.get("mandarin_translation"),
    )


def stage_render_pdfs(config: AppConfig, context: StageContext) -> None:
    """Render and audit the final multilingual PDFs.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with PDF paths and audit reports.

    Raises
    ------
    ValueError
        If either translation package fails structural QA or the final PDF
        audits fail renderability requirements.
    """

    if "english_master" not in context and not config.english_master_output_path.exists():
        stage_freeze_english(config, context)
    if "spanish_translation" not in context and not config.spanish_translation_output_path.exists():
        stage_translate_spanish(config, context)
    if "mandarin_translation" not in context and not config.mandarin_translation_output_path.exists():
        stage_translate_mandarin(config, context)
    if "spanish_qa_report" not in context:
        stage_qa_spanish(config, context)
    if "mandarin_qa_report" not in context:
        stage_qa_mandarin(config, context)

    if not translation_report_is_renderable(context["spanish_qa_report"]):
        raise ValueError(
            "Cannot render PDFs: Spanish translation failed required structural QA for the body/citations package"
        )
    if not translation_report_is_renderable(context["mandarin_qa_report"]):
        raise ValueError(
            "Cannot render PDFs: Mandarin translation failed required structural QA for the body/citations package"
        )

    context["pdf_outputs"] = render_pdfs(config)
    context["pdf_audit_reports"] = audit_rendered_pdfs(config)
    if not pdf_audit_reports_are_renderable(context["pdf_audit_reports"]):
        raise ValueError("Cannot promote PDFs: final artifact audit failed")


def stage_write_manifest(config: AppConfig, context: StageContext) -> None:
    """Write the final run manifest after outputs have been promoted.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The context is updated in place with the final manifest model.
    """

    if "spanish_qa_report" not in context and not config.spanish_qa_report_path.exists():
        stage_qa_spanish(config, context)
    if "mandarin_qa_report" not in context and not config.mandarin_qa_report_path.exists():
        stage_qa_mandarin(config, context)
    if "pdf_outputs" not in context and not (
        config.english_pdf_output_path.exists()
        and config.spanish_pdf_output_path.exists()
        and config.mandarin_pdf_output_path.exists()
        and all(path.exists() for path in pdf_audit_report_paths(config))
    ):
        stage_render_pdfs(config, context)

    context["final_manifest"] = write_manifest(config)


def get_stage_registry() -> dict[str, StageHandler]:
    """Return the mapping from stage names to stage handlers.

    Returns
    -------
    dict of str to StageHandler
        Registry used by the CLI to resolve stage execution.
    """

    return {
        "ingest": stage_ingest,
        "normalize": stage_normalize,
        "index": stage_index,
        "extract_metaphors": stage_extract_metaphors,
        "build_evidence_ledger": stage_build_evidence_ledger,
        "plan_outline": stage_plan_outline,
        "draft_english": stage_draft_english,
        "verify_english": stage_verify_english,
        "critique_english": stage_critique_english,
        "freeze_english": stage_freeze_english,
        "translate_spanish": stage_translate_spanish,
        "qa_spanish": stage_qa_spanish,
        "translate_mandarin": stage_translate_mandarin,
        "qa_mandarin": stage_qa_mandarin,
        "render_pdfs": stage_render_pdfs,
        "write_manifest": stage_write_manifest,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the orchestrator.

    Returns
    -------
    argparse.ArgumentParser
        CLI parser supporting config-path and stage-selection arguments.
    """

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
    """Resolve the stage sequence requested by the CLI.

    Parameters
    ----------
    requested_stage : str
        Requested stage name or ``all``.
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    list of str
        Ordered stage names to execute.

    Raises
    ------
    NotImplementedError
        If the requested stage is configured but has no implementation.
    ValueError
        If the requested stage is not supported by configuration.
    """

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
    """Execute a single pipeline stage with timing and logging.

    Parameters
    ----------
    stage_name : str
        Name of the stage to execute.
    config : AppConfig
        Validated application configuration.
    context : dict of str to Any
        Mutable stage context shared across the current CLI invocation.

    Returns
    -------
    None
        The target stage mutates the context in place.
    """

    registry = get_stage_registry()
    LOGGER.info("Starting stage: %s", stage_name)
    started_at = time.perf_counter()
    registry[stage_name](config, context)
    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    LOGGER.info("Finished stage: %s (%.3f seconds)", stage_name, elapsed_seconds)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI orchestrator entry point.

    Parameters
    ----------
    argv : list of str or None, optional
        Optional argument vector. When ``None``, arguments are read from the
        process command line.

    Returns
    -------
    int
        Process exit code.

    Notes
    -----
    The function logs failures through the configured logger when logging has
    already been initialized, otherwise it emits a parser error message.
    """

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        configure_logging(config)
        stages = resolve_stage_sequence(args.run, config)
        pipeline_started_at = time.perf_counter()

        context: StageContext = {}
        for stage_name in stages:
            run_stage(stage_name, config, context)

        total_elapsed_seconds = round(time.perf_counter() - pipeline_started_at, 3)
        LOGGER.info("Completed requested pipeline stages: %s", ", ".join(stages))
        LOGGER.info("Total pipeline time: %.3f seconds", total_elapsed_seconds)
        return 0
    except Exception as exc:
        if logging.getLogger().handlers:
            LOGGER.exception("Pipeline execution failed: %s", exc)
        else:
            parser.exit(status=1, message=f"Pipeline execution failed: {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
