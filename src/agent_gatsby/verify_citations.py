"""
Deterministic English quote and citation verification for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.index_text import load_passage_index
from agent_gatsby.plan_outline import load_evidence_records
from agent_gatsby.schemas import EvidenceRecord, PassageIndex, PassageRecord, VerificationIssue, VerificationReport

LOGGER = logging.getLogger(__name__)

CITATION_RE = re.compile(r"\[(\d+\.\d+)\]")
ANY_BRACKET_RE = re.compile(r"\[([^\]]+)\]")
DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")


def load_english_draft(source: AppConfig | str | Path) -> str:
    if isinstance(source, AppConfig):
        path = source.draft_output_path
    else:
        path = Path(source)
    return path.read_text(encoding="utf-8")


def build_passage_lookup(passage_index: PassageIndex) -> dict[str, PassageRecord]:
    return {passage.passage_id: passage for passage in passage_index.passages}


def build_evidence_lookup(evidence_records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    lookup: dict[str, list[EvidenceRecord]] = {}
    for record in evidence_records:
        lookup.setdefault(record.passage_id, []).append(record)
    return lookup


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def normalize_match_text(text: str, *, normalize_curly_quotes: bool) -> str:
    normalized = text
    if normalize_curly_quotes:
        normalized = (
            normalized.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
    return collapse_spaces(normalized).strip()


def extract_citation_markers(text: str) -> list[str]:
    return [match.group(1) for match in CITATION_RE.finditer(text)]


def extract_invalid_bracket_markers(text: str) -> list[str]:
    invalid: list[str] = []
    for match in ANY_BRACKET_RE.finditer(text):
        if not CITATION_RE.fullmatch(match.group(0)):
            invalid.append(match.group(0))
    return invalid


def extract_quoted_strings(text: str) -> list[str]:
    quotes: list[str] = []
    for pattern in (DOUBLE_QUOTE_RE, SINGLE_QUOTE_RE):
        for match in pattern.finditer(text):
            candidate = collapse_spaces(match.group(1)).strip()
            if candidate:
                quotes.append(candidate)
    return quotes


def paragraph_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def build_issue(code: str, message: str, *, passage_id: str | None = None, evidence_id: str | None = None) -> VerificationIssue:
    return VerificationIssue(
        code=code,
        message=message,
        passage_id=passage_id,
        evidence_id=evidence_id,
    )


def validate_citations(
    text: str,
    *,
    passage_lookup: dict[str, PassageRecord],
    evidence_lookup: dict[str, list[EvidenceRecord]],
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []

    invalid_markers = extract_invalid_bracket_markers(text)
    for marker in invalid_markers:
        issues.append(build_issue("invalid_citation_format", f"Invalid bracket marker found in draft: {marker}"))

    citation_markers = extract_citation_markers(text)
    if not citation_markers:
        issues.append(build_issue("missing_citations", "Draft does not contain any valid [chapter.paragraph] citations"))
        return issues

    for marker in citation_markers:
        if marker not in passage_lookup:
            issues.append(build_issue("missing_passage_locator", f"Citation does not resolve to a passage: [{marker}]"))
            continue
        if marker not in evidence_lookup:
            issues.append(build_issue("missing_evidence_link", f"Citation does not map to any verified evidence: [{marker}]", passage_id=marker))

    return issues


def validate_quotes(
    text: str,
    *,
    passage_lookup: dict[str, PassageRecord],
    evidence_lookup: dict[str, list[EvidenceRecord]],
    normalize_curly_quotes: bool,
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []

    for block in paragraph_blocks(text):
        citations = extract_citation_markers(block)
        quotes = extract_quoted_strings(block)
        if not quotes:
            continue

        if not citations:
            for quote in quotes:
                issues.append(build_issue("missing_quote_citation", f'Quoted text is missing a citation: "{quote}"'))
            continue

        normalized_citations = [marker for marker in citations if marker in passage_lookup]
        for quote in quotes:
            normalized_quote = normalize_match_text(quote, normalize_curly_quotes=normalize_curly_quotes)
            matching_passage_ids = [
                marker
                for marker in normalized_citations
                if normalized_quote in normalize_match_text(
                    passage_lookup[marker].text,
                    normalize_curly_quotes=normalize_curly_quotes,
                )
            ]
            if not matching_passage_ids:
                issues.append(
                    build_issue(
                        "quote_not_in_passage",
                        f'Quoted text does not exact-match any cited passage: "{quote}"',
                    )
                )
                continue

            matching_evidence: list[EvidenceRecord] = []
            for passage_id in matching_passage_ids:
                for record in evidence_lookup.get(passage_id, []):
                    if normalized_quote == normalize_match_text(record.quote, normalize_curly_quotes=normalize_curly_quotes):
                        matching_evidence.append(record)

            if not matching_evidence:
                issues.append(
                    build_issue(
                        "quote_not_in_evidence",
                        f'Quoted text does not match any verified evidence quote for cited passages: "{quote}"',
                    )
                )

    return issues


def write_verification_report(config: AppConfig, report: VerificationReport) -> None:
    output_path = config.english_verification_report_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote English verification report to %s", output_path)


def verify_english_draft(
    config: AppConfig,
    *,
    draft_text: str | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    passage_index: PassageIndex | None = None,
) -> VerificationReport:
    loaded_text = draft_text or load_english_draft(config)
    loaded_records = evidence_records or load_evidence_records(config)
    loaded_index = passage_index or load_passage_index(config)

    passage_lookup = build_passage_lookup(loaded_index)
    evidence_lookup = build_evidence_lookup(loaded_records)
    normalize_curly_quotes = bool(config.verification.get("normalize_curly_quotes_for_matching", True))

    issues = [
        *validate_citations(loaded_text, passage_lookup=passage_lookup, evidence_lookup=evidence_lookup),
        *validate_quotes(
            loaded_text,
            passage_lookup=passage_lookup,
            evidence_lookup=evidence_lookup,
            normalize_curly_quotes=normalize_curly_quotes,
        ),
    ]

    report = VerificationReport(
        stage="verify_english",
        status="passed" if not issues else "failed",
        generated_at=utc_now_iso(),
        issues=issues,
    )
    write_verification_report(config, report)

    quote_count = len(extract_quoted_strings(loaded_text))
    citation_count = len(extract_citation_markers(loaded_text))
    LOGGER.info(
        "English verification completed with %d quotes, %d citations, %d issues",
        quote_count,
        citation_count,
        len(issues),
    )

    if issues and (
        config.verification.get("fail_on_quote_mismatch", True)
        or config.verification.get("fail_on_invalid_citation", True)
    ):
        raise ValueError(f"English verification failed with {len(issues)} issue(s)")

    return report
