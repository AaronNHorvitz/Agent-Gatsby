"""Deterministic English quote and citation verification.

This module verifies that the drafted English analysis remains grounded in the
locked source text and verified evidence ledger. It aligns near-miss direct
quotes to canonical evidence when safe, validates citation resolution, writes a
verification report, and emits a machine-readable citation registry for later
rendering stages.
"""

from __future__ import annotations

from difflib import SequenceMatcher
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
    """Load the English draft from disk.

    Parameters
    ----------
    source : AppConfig or str or Path
        Configuration object or direct path to the draft artifact.

    Returns
    -------
    str
        English draft markdown.
    """

    if isinstance(source, AppConfig):
        path = source.draft_output_path
    else:
        path = Path(source)
    return path.read_text(encoding="utf-8")


def build_passage_lookup(passage_index: PassageIndex) -> dict[str, PassageRecord]:
    """Build a passage lookup keyed by passage identifier.

    Parameters
    ----------
    passage_index : PassageIndex
        Loaded passage index.

    Returns
    -------
    dict of str to PassageRecord
        Lookup table keyed by ``passage_id``.
    """

    return {passage.passage_id: passage for passage in passage_index.passages}


def build_evidence_lookup(evidence_records: list[EvidenceRecord]) -> dict[str, list[EvidenceRecord]]:
    """Group evidence records by passage identifier.

    Parameters
    ----------
    evidence_records : list of EvidenceRecord
        Verified evidence ledger.

    Returns
    -------
    dict of str to list of EvidenceRecord
        Evidence records grouped by ``passage_id``.
    """

    lookup: dict[str, list[EvidenceRecord]] = {}
    for record in evidence_records:
        lookup.setdefault(record.passage_id, []).append(record)
    return lookup


def collapse_spaces(text: str) -> str:
    """Collapse repeated whitespace to single spaces.

    Parameters
    ----------
    text : str
        Source text.

    Returns
    -------
    str
        Whitespace-normalized text.
    """

    return " ".join(text.split())


def count_words(text: str) -> int:
    """Count words in draft text while ignoring markdown brackets and headings.

    Parameters
    ----------
    text : str
        Draft text to count.

    Returns
    -------
    int
        Approximate word count.
    """

    cleaned = ANY_BRACKET_RE.sub("", text.replace("#", " ").replace("_", " "))
    return len(re.findall(r"\b[\w'-]+\b", cleaned, flags=re.UNICODE))


def estimate_page_count(word_count: int, words_per_page: int) -> float:
    """Estimate page count from a word-count heuristic.

    Parameters
    ----------
    word_count : int
        Total word count.
    words_per_page : int
        Configured words-per-page heuristic.

    Returns
    -------
    float
        Estimated page count rounded to two decimals.
    """

    if words_per_page <= 0:
        return 0.0
    return round(word_count / words_per_page, 2)


def normalize_match_text(text: str, *, normalize_curly_quotes: bool) -> str:
    """Normalize text for exact quote comparison.

    Parameters
    ----------
    text : str
        Text to normalize.
    normalize_curly_quotes : bool
        Whether curly quotes should be converted to straight quotes first.

    Returns
    -------
    str
        Whitespace-normalized comparison string.
    """

    normalized = text
    if normalize_curly_quotes:
        normalized = (
            normalized.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
    return collapse_spaces(normalized).strip()


def normalize_loose_quote_match(text: str, *, normalize_curly_quotes: bool) -> str:
    """Normalize text for case-insensitive loose quote matching.

    Parameters
    ----------
    text : str
        Text to normalize.
    normalize_curly_quotes : bool
        Whether curly quotes should be converted to straight quotes first.

    Returns
    -------
    str
        Lowercased normalization used for loose similarity matching.
    """

    return normalize_match_text(text, normalize_curly_quotes=normalize_curly_quotes).lower()


def extract_citation_markers(text: str) -> list[str]:
    """Extract resolved passage identifiers from citation markers.

    Parameters
    ----------
    text : str
        Draft text to scan.

    Returns
    -------
    list of str
        Passage identifiers referenced by citations in source order.
    """

    return extract_citation_passage_ids(text)


def extract_quoted_strings(text: str) -> list[str]:
    """Extract double-quoted strings from draft text.

    Parameters
    ----------
    text : str
        Draft text to scan.

    Returns
    -------
    list of str
        Whitespace-normalized quoted spans.
    """

    quotes: list[str] = []
    for match in DOUBLE_QUOTE_RE.finditer(text):
        candidate = collapse_spaces(match.group(1)).strip()
        if candidate:
            quotes.append(candidate)
    return quotes


def paragraph_blocks(text: str) -> list[str]:
    """Split markdown text into paragraph-like blocks.

    Parameters
    ----------
    text : str
        Draft text to split.

    Returns
    -------
    list of str
        Non-empty blocks separated by blank lines.
    """

    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def quote_validation_blocks(text: str) -> list[str]:
    """Split text into blocks used for quote validation.

    Parameters
    ----------
    text : str
        Draft text to inspect.

    Returns
    -------
    list of str
        Paragraph blocks, with ``Metaphor text`` block quotes split into
        line-level validation units where appropriate.
    """

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
    """Extract quotes from a validation block.

    Parameters
    ----------
    block : str
        Block returned by :func:`quote_validation_blocks`.

    Returns
    -------
    list of str
        Quotes that should be checked against source passages.
    """

    stripped = block.strip()
    blockquote_match = BLOCKQUOTE_QUOTE_LINE_RE.match(stripped)
    if blockquote_match:
        candidate = collapse_spaces(blockquote_match.group("quote")).strip()
        return [candidate] if candidate else []
    return extract_quoted_strings(block)


def split_main_text_and_appendix(text: str, *, appendix_heading: str) -> tuple[str, str | None]:
    """Split report text into main body and citations appendix.

    Parameters
    ----------
    text : str
        Full draft text.
    appendix_heading : str
        Heading used for the citations appendix.

    Returns
    -------
    tuple of (str, str or None)
        Main report body and the appendix block when present.
    """

    appendix_marker = f"## {appendix_heading}"
    if appendix_marker not in text:
        return text, None
    body_text, appendix_text = text.split(appendix_marker, maxsplit=1)
    return body_text.strip(), appendix_marker + appendix_text


def find_canonical_quote_replacement(
    quote: str,
    *,
    cited_passage_ids: list[str],
    evidence_lookup: dict[str, list[EvidenceRecord]],
    normalize_curly_quotes: bool,
) -> str | None:
    """Find a safe canonical quote replacement for a cited near-match.

    Parameters
    ----------
    quote : str
        Quoted text found in the draft.
    cited_passage_ids : list of str
        Passage identifiers cited by the enclosing block.
    evidence_lookup : dict of str to list of EvidenceRecord
        Verified evidence records grouped by passage identifier.
    normalize_curly_quotes : bool
        Whether curly quotes should be normalized before matching.

    Returns
    -------
    str or None
        Canonical replacement quote when a single safe match can be inferred,
        otherwise ``None``.
    """

    normalized_quote = normalize_match_text(quote, normalize_curly_quotes=normalize_curly_quotes)
    loose_quote = normalize_loose_quote_match(quote, normalize_curly_quotes=normalize_curly_quotes)
    candidates: list[str] = []

    for passage_id in cited_passage_ids:
        for record in evidence_lookup.get(passage_id, []):
            candidate = collapse_spaces(record.quote).strip()
            if not candidate:
                continue
            if normalize_match_text(candidate, normalize_curly_quotes=normalize_curly_quotes) == normalized_quote:
                return None
            if normalize_loose_quote_match(candidate, normalize_curly_quotes=normalize_curly_quotes) == loose_quote:
                candidates.append(candidate)

    unique_candidates = list(dict.fromkeys(candidates))
    if len(unique_candidates) == 1:
        return unique_candidates[0]

    similarity_candidates: list[tuple[float, str]] = []
    for passage_id in cited_passage_ids:
        for record in evidence_lookup.get(passage_id, []):
            candidate = collapse_spaces(record.quote).strip()
            if not candidate:
                continue
            candidate_ratio = SequenceMatcher(
                None,
                loose_quote,
                normalize_loose_quote_match(candidate, normalize_curly_quotes=normalize_curly_quotes),
            ).ratio()
            if candidate_ratio >= 0.9:
                similarity_candidates.append((candidate_ratio, candidate))

    unique_similarity_candidates: list[tuple[float, str]] = []
    seen_candidates: set[str] = set()
    for ratio, candidate in sorted(similarity_candidates, reverse=True):
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        unique_similarity_candidates.append((ratio, candidate))

    if len(unique_similarity_candidates) == 1:
        return unique_similarity_candidates[0][1]
    if len(unique_similarity_candidates) > 1:
        best_ratio, best_candidate = unique_similarity_candidates[0]
        next_ratio = unique_similarity_candidates[1][0]
        if best_ratio - next_ratio >= 0.05:
            return best_candidate
    return None


def repair_cited_quote_alignment(
    text: str,
    *,
    evidence_records: list[EvidenceRecord],
    passage_index: PassageIndex,
    appendix_heading: str,
    normalize_curly_quotes: bool,
) -> tuple[str, list[dict[str, str]]]:
    """Repair near-miss direct quotes against cited evidence when safe.

    Parameters
    ----------
    text : str
        Draft text to repair.
    evidence_records : list of EvidenceRecord
        Verified evidence ledger.
    passage_index : PassageIndex
        Loaded passage index.
    appendix_heading : str
        Heading used for the citations appendix.
    normalize_curly_quotes : bool
        Whether curly quotes should be normalized before matching.

    Returns
    -------
    tuple of (str, list of dict of str to str)
        Repaired draft text and a list of applied quote replacements.
    """

    main_text, appendix_text = split_main_text_and_appendix(text, appendix_heading=appendix_heading)
    evidence_lookup = build_evidence_lookup(evidence_records)
    passage_lookup = build_passage_lookup(passage_index)
    repaired_blocks: list[str] = []
    repairs: list[dict[str, str]] = []

    for block in quote_validation_blocks(main_text):
        cited_passage_ids = [marker for marker in extract_citation_markers(block) if marker in passage_lookup]
        if not cited_passage_ids:
            repaired_blocks.append(block)
            continue

        matches = list(DOUBLE_QUOTE_RE.finditer(block))
        if not matches:
            repaired_blocks.append(block)
            continue

        repaired_block = block
        for match in reversed(matches):
            quoted_text = collapse_spaces(match.group(1)).strip()
            if not quoted_text:
                continue
            replacement = find_canonical_quote_replacement(
                quoted_text,
                cited_passage_ids=cited_passage_ids,
                evidence_lookup=evidence_lookup,
                normalize_curly_quotes=normalize_curly_quotes,
            )
            if not replacement or replacement == quoted_text:
                continue
            repaired_block = (
                repaired_block[: match.start(1)]
                + replacement
                + repaired_block[match.end(1) :]
            )
            repairs.append(
                {
                    "quote": quoted_text,
                    "replacement": replacement,
                }
            )

        repaired_blocks.append(repaired_block)

    repaired_main_text = "\n\n".join(repaired_blocks).strip()
    if appendix_text is None:
        return repaired_main_text + "\n", repairs
    return repaired_main_text + "\n\n" + appendix_text.strip() + "\n", repairs


def prose_paragraph_blocks(text: str) -> list[str]:
    """Return prose-only paragraph blocks for unsupported-claim heuristics.

    Parameters
    ----------
    text : str
        Draft text to inspect.

    Returns
    -------
    list of str
        Paragraph blocks that look like prose rather than headings or note
        metadata.
    """

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
    """Split a prose block into approximate sentences.

    Parameters
    ----------
    text : str
        Prose block to split.

    Returns
    -------
    list of str
        Sentence-like spans with trivial fragments removed.
    """

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
    """Return whether a prose paragraph resolves to verified evidence.

    Parameters
    ----------
    paragraph : str
        Prose paragraph to inspect.
    passage_lookup : dict of str to PassageRecord
        Passage lookup keyed by ``passage_id``.
    evidence_lookup : dict of str to list of EvidenceRecord
        Evidence records grouped by passage identifier.

    Returns
    -------
    bool
        ``True`` when the paragraph includes at least one citation that maps to
        both a known passage and verified evidence.
    """

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
    """Compute unsupported-claim heuristic metrics for the draft.

    Parameters
    ----------
    text : str
        Draft text to inspect.
    passage_lookup : dict of str to PassageRecord
        Passage lookup keyed by ``passage_id``.
    evidence_lookup : dict of str to list of EvidenceRecord
        Evidence records grouped by passage identifier.

    Returns
    -------
    tuple of (int, int, float)
        Prose sentence count, unsupported sentence count, and unsupported
        sentence ratio.
    """

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
    """Build a structured verification issue record.

    Parameters
    ----------
    code : str
        Stable issue code.
    message : str
        Human-readable issue description.
    passage_id : str or None, optional
        Source passage implicated in the issue.
    evidence_id : str or None, optional
        Evidence record implicated in the issue.

    Returns
    -------
    VerificationIssue
        Structured verification issue.
    """

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
    """Validate citation syntax and passage/evidence resolution.

    Parameters
    ----------
    text : str
        Draft text to validate.
    passage_lookup : dict of str to PassageRecord
        Passage lookup keyed by ``passage_id``.
    evidence_lookup : dict of str to list of EvidenceRecord
        Evidence records grouped by passage identifier.

    Returns
    -------
    list of VerificationIssue
        Citation-related verification issues.
    """

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
    """Validate quoted text against cited passages and verified evidence.

    Parameters
    ----------
    text : str
        Draft text to validate.
    passage_lookup : dict of str to PassageRecord
        Passage lookup keyed by ``passage_id``.
    evidence_lookup : dict of str to list of EvidenceRecord
        Evidence records grouped by passage identifier.
    normalize_curly_quotes : bool
        Whether curly quotes should be normalized before comparison.

    Returns
    -------
    list of VerificationIssue
        Quote-related verification issues.
    """

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
    """Count issues belonging to a selected issue-code set.

    Parameters
    ----------
    issues : list of VerificationIssue
        Issues to count.
    issue_codes : set of str
        Codes considered part of the target category.

    Returns
    -------
    int
        Count of matching issues.
    """

    return sum(1 for issue in issues if issue.code in issue_codes)


def capped_rate(failure_count: int, total_count: int) -> float:
    """Compute a bounded failure rate.

    Parameters
    ----------
    failure_count : int
        Number of failures.
    total_count : int
        Number of attempted checks.

    Returns
    -------
    float
        Failure rate capped to the inclusive range ``[0.0, 1.0]``.
    """

    if failure_count <= 0:
        return 0.0
    if total_count <= 0:
        return 1.0
    return round(min(1.0, failure_count / total_count), 4)


def write_verification_report(config: AppConfig, report: VerificationReport) -> None:
    """Write the English verification report to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    report : VerificationReport
        Verification report to serialize.

    Returns
    -------
    None
        The report is written to the configured artifact path.
    """

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
    """Verify the English draft against passages, evidence, and thresholds.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    draft_text : str or None, optional
        Preloaded draft text. When omitted, the stage loads the draft from
        disk.
    evidence_records : list of EvidenceRecord or None, optional
        Preloaded evidence ledger. When omitted, the stage loads the ledger
        from disk.
    passage_index : PassageIndex or None, optional
        Preloaded passage index. When omitted, the stage loads the index from
        disk.

    Returns
    -------
    VerificationReport
        Structured verification report written to disk.

    Raises
    ------
    ValueError
        If verification fails and the configuration requires quote or citation
        failures to halt promotion.
    """

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
