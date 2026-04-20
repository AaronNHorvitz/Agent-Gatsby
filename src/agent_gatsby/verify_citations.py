"""
Deterministic English quote and citation verification for Agent Gatsby.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from agent_gatsby.citation_registry import (
    ANY_BRACKET_RE,
    build_citation_registry,
    extract_citation_passage_ids,
    extract_invalid_bracket_markers,
    write_citation_registry,
)
from agent_gatsby.config import AppConfig
from agent_gatsby.data_ingest import utc_now_iso
from agent_gatsby.index_text import load_passage_index
from agent_gatsby.plan_outline import load_evidence_records
from agent_gatsby.schemas import EvidenceRecord, PassageIndex, PassageRecord, VerificationIssue, VerificationReport

LOGGER = logging.getLogger(__name__)

DOUBLE_QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)
SINGLE_QUOTE_RE = re.compile(r"(?<!\w)['‘]([^'\n]{2,}?)['’](?!\w)")
BLOCKQUOTE_QUOTE_LINE_RE = re.compile(r'^\s*>\s*"(?P<quote>.+)"\s+(?P<citation>\[[^\]]+\])\s*$')
QUOTE_ISSUE_CODES = {
    "quote_not_in_passage",
    "quote_not_in_evidence",
}
CITATION_ISSUE_CODES = {
    "invalid_citation_format",
    "missing_citations",
    "missing_passage_locator",
    "missing_evidence_link",
    "missing_quote_citation",
}


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


def count_words(text: str) -> int:
    cleaned = ANY_BRACKET_RE.sub("", text.replace("#", " ").replace("_", " "))
    return len(re.findall(r"\b[\w'-]+\b", cleaned, flags=re.UNICODE))


def estimate_page_count(word_count: int, words_per_page: int) -> float:
    if words_per_page <= 0:
        return 0.0
    return round(word_count / words_per_page, 2)


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
    return extract_citation_passage_ids(text)


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


def quote_validation_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for block in paragraph_blocks(text):
        if "Metaphor text:" not in block:
            blocks.append(block)
            continue
        quote_lines = [
            line.strip()
            for line in block.splitlines()
            if BLOCKQUOTE_QUOTE_LINE_RE.match(line.strip())
        ]
        if quote_lines:
            blocks.extend(quote_lines)
            continue
        blocks.append(block)
    return blocks


def extract_validation_quotes(block: str) -> list[str]:
    stripped = block.strip()
    blockquote_match = BLOCKQUOTE_QUOTE_LINE_RE.match(stripped)
    if blockquote_match:
        candidate = collapse_spaces(blockquote_match.group("quote")).strip()
        return [candidate] if candidate else []
    return extract_quoted_strings(block)


def split_main_text_and_appendix(text: str, *, appendix_heading: str) -> tuple[str, str | None]:
    appendix_marker = f"## {appendix_heading}"
    if appendix_marker not in text:
        return text, None
    body_text, appendix_text = text.split(appendix_marker, maxsplit=1)
    return body_text.strip(), appendix_marker + appendix_text


def prose_paragraph_blocks(text: str) -> list[str]:
    prose_blocks: list[str] = []
    for block in paragraph_blocks(text):
        normalized = collapse_spaces(block.strip().strip("_"))
        if not normalized:
            continue
        if normalized.startswith("#"):
            continue
        if normalized.lower().startswith("citation note:"):
            continue
        prose_blocks.append(block)
    return prose_blocks


def split_sentences(text: str) -> list[str]:
    cleaned = collapse_spaces(ANY_BRACKET_RE.sub("", text)).strip(" _")
    if not cleaned:
        return []
    sentences = [
        sentence.strip(" _")
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if sentence.strip(" _")
    ]
    return [sentence for sentence in sentences if len(sentence.split()) >= 3]


def paragraph_has_resolved_citation(
    paragraph: str,
    *,
    passage_lookup: dict[str, PassageRecord],
    evidence_lookup: dict[str, list[EvidenceRecord]],
) -> bool:
    for marker in extract_citation_markers(paragraph):
        if marker in passage_lookup and marker in evidence_lookup:
            return True
    return False


def compute_unsupported_sentence_metrics(
    text: str,
    *,
    passage_lookup: dict[str, PassageRecord],
    evidence_lookup: dict[str, list[EvidenceRecord]],
) -> tuple[int, int, float]:
    prose_sentence_count = 0
    unsupported_sentence_count = 0

    for block in prose_paragraph_blocks(text):
        sentences = split_sentences(block)
        if not sentences:
            continue
        prose_sentence_count += len(sentences)
        if not paragraph_has_resolved_citation(
            block,
            passage_lookup=passage_lookup,
            evidence_lookup=evidence_lookup,
        ):
            unsupported_sentence_count += len(sentences)

    if prose_sentence_count == 0:
        return 0, 0, 0.0

    return (
        prose_sentence_count,
        unsupported_sentence_count,
        round(unsupported_sentence_count / prose_sentence_count, 4),
    )


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
        issues.append(build_issue("missing_citations", "Draft does not contain any valid citations"))
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

    for block in quote_validation_blocks(text):
        citations = extract_citation_markers(block)
        quotes = extract_validation_quotes(block)
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


def count_issues_for_codes(issues: list[VerificationIssue], issue_codes: set[str]) -> int:
    return sum(1 for issue in issues if issue.code in issue_codes)


def capped_rate(failure_count: int, total_count: int) -> float:
    if failure_count <= 0:
        return 0.0
    if total_count <= 0:
        return 1.0
    return round(min(1.0, failure_count / total_count), 4)


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
    appendix_heading = str(config.drafting.get("citation_appendix_heading", "Citations"))
    main_text, _ = split_main_text_and_appendix(loaded_text, appendix_heading=appendix_heading)

    passage_lookup = build_passage_lookup(loaded_index)
    evidence_lookup = build_evidence_lookup(loaded_records)
    normalize_curly_quotes = bool(config.verification.get("normalize_curly_quotes_for_matching", True))

    issues = [
        *validate_citations(main_text, passage_lookup=passage_lookup, evidence_lookup=evidence_lookup),
        *validate_quotes(
            main_text,
            passage_lookup=passage_lookup,
            evidence_lookup=evidence_lookup,
            normalize_curly_quotes=normalize_curly_quotes,
        ),
    ]

    citation_registry = build_citation_registry(
        main_text,
        loaded_index,
        display_format=str(config.drafting.get("display_citation_format", "[{citation_number}]")),
    )
    write_citation_registry(config, citation_registry)

    word_count = count_words(loaded_text)
    words_per_page = int(config.drafting.get("words_per_page_estimate", 280))
    estimated_pages = estimate_page_count(word_count, words_per_page)
    quote_count = len(extract_quoted_strings(main_text))
    citation_count = len(extract_citation_markers(main_text))
    invalid_quote_issue_count = count_issues_for_codes(issues, QUOTE_ISSUE_CODES)
    invalid_citation_issue_count = count_issues_for_codes(issues, CITATION_ISSUE_CODES)
    quote_checks_total = quote_count
    citation_checks_total = citation_count or (1 if invalid_citation_issue_count else 0)
    prose_sentence_count, unsupported_sentence_count, unsupported_sentence_ratio = compute_unsupported_sentence_metrics(
        main_text,
        passage_lookup=passage_lookup,
        evidence_lookup=evidence_lookup,
    )

    report = VerificationReport(
        stage="verify_english",
        status="passed" if not issues else "failed",
        generated_at=utc_now_iso(),
        word_count=word_count,
        estimated_pages=estimated_pages,
        quote_checks_total=quote_checks_total,
        quote_checks_passed=max(quote_checks_total - invalid_quote_issue_count, 0),
        citation_checks_total=citation_checks_total,
        citation_checks_passed=max(citation_checks_total - invalid_citation_issue_count, 0),
        invalid_quote_rate=capped_rate(invalid_quote_issue_count, quote_checks_total),
        invalid_citation_rate=capped_rate(invalid_citation_issue_count, citation_checks_total),
        prose_sentence_count=prose_sentence_count,
        unsupported_sentence_count=unsupported_sentence_count,
        unsupported_sentence_ratio=unsupported_sentence_ratio,
        issues=issues,
    )
    write_verification_report(config, report)

    LOGGER.info(
        "English verification completed with %d words, %.2f estimated pages, %d quotes, %d citations, and %d issues",
        word_count,
        estimated_pages,
        quote_count,
        citation_count,
        len(issues),
    )

    target_minimum_words = int(config.drafting.get("target_word_count_min", 0))
    target_maximum_words = int(config.drafting.get("target_word_count_max", 0))
    if target_minimum_words > 0 and word_count < target_minimum_words:
        LOGGER.warning("Verified English draft is below target word count: %d < %d", word_count, target_minimum_words)
    if target_maximum_words > 0 and word_count > target_maximum_words:
        LOGGER.warning("Verified English draft is above target word count: %d > %d", word_count, target_maximum_words)

    invalid_quote_rate_threshold = float(config.verification.get("invalid_quote_rate_threshold", 0.0))
    if report.invalid_quote_rate is not None and report.invalid_quote_rate > invalid_quote_rate_threshold:
        LOGGER.warning(
            "Invalid quote rate exceeds threshold: %.4f > %.4f",
            report.invalid_quote_rate,
            invalid_quote_rate_threshold,
        )

    invalid_citation_rate_threshold = float(config.verification.get("invalid_citation_rate_threshold", 0.0))
    if report.invalid_citation_rate is not None and report.invalid_citation_rate > invalid_citation_rate_threshold:
        LOGGER.warning(
            "Invalid citation rate exceeds threshold: %.4f > %.4f",
            report.invalid_citation_rate,
            invalid_citation_rate_threshold,
        )

    unsupported_threshold = float(config.verification.get("unsupported_claim_ratio_threshold", 0.10))
    if unsupported_sentence_ratio > unsupported_threshold:
        LOGGER.warning(
            "Unsupported-claim heuristic exceeds advisory threshold: %.4f > %.4f",
            unsupported_sentence_ratio,
            unsupported_threshold,
        )

    if issues and (
        config.verification.get("fail_on_quote_mismatch", True)
        or config.verification.get("fail_on_invalid_citation", True)
    ):
        raise ValueError(f"English verification failed with {len(issues)} issue(s)")

    return report
