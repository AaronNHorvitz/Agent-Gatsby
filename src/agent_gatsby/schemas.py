"""Pydantic schemas for serialized pipeline artifacts.

This module defines the structured records written and read across the Agent
Gatsby pipeline. These schemas keep intermediate artifacts explicit and
machine-validatable so drafting, verification, translation, and rendering
stages can coordinate through stable JSON and markdown side products.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceManifest(BaseModel):
    """Metadata describing the locked source text used for a run.

    Attributes
    ----------
    source_name : str
        Human-readable source identifier.
    source_path : str
        Repository-relative path to the source file.
    encoding : str
        Encoding used to decode the source text.
    sha256 : str
        SHA-256 hash of the raw source bytes.
    file_size_bytes : int
        Source file size in bytes.
    generated_at : str
        UTC timestamp for manifest creation.
    normalized_output_path : str or None, optional
        Path where normalized source text is written.
    chapter_count : int or None, optional
        Number of chapters detected after normalization.
    paragraph_count : int or None, optional
        Number of paragraphs detected after normalization.
    """

    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_path: str
    encoding: str
    sha256: str
    file_size_bytes: int
    generated_at: str
    normalized_output_path: str | None = None
    chapter_count: int | None = None
    paragraph_count: int | None = None


class PassageRecord(BaseModel):
    """Addressable passage extracted from the normalized source text.

    Attributes
    ----------
    passage_id : str
        Stable ``chapter.paragraph`` identifier.
    chapter : int
        Chapter number for the passage.
    paragraph : int
        Paragraph number within the chapter.
    text : str
        Exact passage text used for verification and drafting.
    char_start : int
        Inclusive character offset in the normalized text.
    char_end : int
        Exclusive character offset in the normalized text.
    """

    model_config = ConfigDict(extra="forbid")

    passage_id: str
    chapter: int
    paragraph: int
    text: str
    char_start: int
    char_end: int


class PassageIndex(BaseModel):
    """Collection of indexed passages derived from the normalized source.

    Attributes
    ----------
    source_name : str
        Identifier for the normalized source text.
    normalized_path : str
        Path to the normalized source file.
    chapter_count : int
        Number of chapters represented in the index.
    passage_count : int
        Number of indexed passages.
    generated_at : str
        UTC timestamp for index generation.
    passages : list of PassageRecord
        Indexed passages in deterministic source order.
    """

    model_config = ConfigDict(extra="forbid")

    source_name: str
    normalized_path: str
    chapter_count: int
    passage_count: int
    generated_at: str
    passages: list[PassageRecord] = Field(default_factory=list)


class MetaphorCandidate(BaseModel):
    """Model-proposed candidate for figurative evidence.

    Attributes
    ----------
    candidate_id : str
        Stable identifier for the candidate.
    label : str
        Short figurative-language label proposed by the model.
    passage_id : str
        Passage identifier from which the quote was extracted.
    quote : str
        Exact quoted span proposed as evidence.
    rationale : str
        Short explanation for why the quote matters.
    confidence : float
        Model-reported confidence score.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    label: str
    passage_id: str
    quote: str
    rationale: str
    confidence: float


class RejectedCandidate(BaseModel):
    """Candidate rejected during evidence-ledger validation.

    Attributes
    ----------
    candidate_id : str
        Identifier of the rejected candidate.
    reason : str
        Human-readable rejection reason.
    passage_id : str or None, optional
        Passage identifier associated with the candidate.
    label : str or None, optional
        Candidate label when available.
    quote : str or None, optional
        Candidate quote when available.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    reason: str
    passage_id: str | None = None
    label: str | None = None
    quote: str | None = None


class EvidenceRecord(BaseModel):
    """Verified evidence record promoted for downstream drafting.

    Attributes
    ----------
    evidence_id : str
        Stable evidence identifier.
    metaphor : str
        Normalized metaphor or figurative-language label.
    quote : str
        Exact verified quote text.
    passage_id : str
        Source passage identifier.
    chapter : int
        Source chapter number.
    interpretation : str
        Short interpretation of the evidence.
    supporting_theme_tags : list of str
        Optional thematic tags for downstream grouping.
    status : str
        Promotion status, typically ``verified``.
    source_candidate_id : str or None, optional
        Original candidate identifier when promoted from extraction output.
    source_type : {"candidate", "manual_override"}, default="candidate"
        Whether the record came from candidate extraction or an explicit manual
        override.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    metaphor: str
    quote: str
    passage_id: str
    chapter: int
    interpretation: str
    supporting_theme_tags: list[str] = Field(default_factory=list)
    status: str
    source_candidate_id: str | None = None
    source_type: Literal["candidate", "manual_override"] = "candidate"


class OutlineSection(BaseModel):
    """Single section in the planned English report outline.

    Attributes
    ----------
    section_id : str
        Stable section identifier.
    heading : str
        Section heading used in drafting and final output.
    purpose : str or None, optional
        Short note describing the section's intended argument.
    evidence_ids : list of str
        Ordered evidence identifiers assigned to the section.
    """

    model_config = ConfigDict(extra="forbid")

    section_id: str
    heading: str
    purpose: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class OutlinePlan(BaseModel):
    """Structured plan for the English report.

    Attributes
    ----------
    title : str
        Report title.
    thesis : str
        Central argument for the report.
    intro_notes : str
        Guidance for the introduction.
    sections : list of OutlineSection
        Ordered body sections.
    conclusion_notes : str
        Guidance for the conclusion.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    thesis: str
    intro_notes: str
    sections: list[OutlineSection] = Field(default_factory=list)
    conclusion_notes: str


class VerificationIssue(BaseModel):
    """Single verification finding produced during QA.

    Attributes
    ----------
    code : str
        Stable issue code.
    message : str
        Human-readable issue description.
    passage_id : str or None, optional
        Source passage implicated in the issue.
    evidence_id : str or None, optional
        Evidence record implicated in the issue.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    passage_id: str | None = None
    evidence_id: str | None = None


class CitationRegistryEntry(BaseModel):
    """Registry entry mapping display citations to canonical passages.

    Attributes
    ----------
    citation_number : int
        Sequential citation note number used in the final report.
    display_label : str
        Human-readable label rendered in the report.
    canonical_locator : str
        Canonical ``chapter.paragraph`` locator.
    passage_id : str
        Source passage identifier.
    chapter : int
        Source chapter number.
    paragraph : int
        Source paragraph number.
    exact_passage_text : str
        Exact locked-source passage text for the citation.
    """

    model_config = ConfigDict(extra="forbid")

    citation_number: int
    display_label: str
    canonical_locator: str
    passage_id: str
    chapter: int
    paragraph: int
    exact_passage_text: str


class VerificationReport(BaseModel):
    """Structured report summarizing English verification results.

    Attributes
    ----------
    stage : str
        Pipeline stage that produced the report.
    status : str
        Overall verification status.
    generated_at : str
        UTC timestamp for report generation.
    word_count : int or None, optional
        Draft word count.
    estimated_pages : float or None, optional
        Estimated page count derived from the configured heuristic.
    quote_checks_total : int or None, optional
        Total number of quote checks attempted.
    quote_checks_passed : int or None, optional
        Number of quote checks that passed.
    citation_checks_total : int or None, optional
        Total number of citation checks attempted.
    citation_checks_passed : int or None, optional
        Number of citation checks that passed.
    invalid_quote_rate : float or None, optional
        Fraction of failed quote checks.
    invalid_citation_rate : float or None, optional
        Fraction of failed citation checks.
    prose_sentence_count : int or None, optional
        Number of prose sentences evaluated for support metrics.
    unsupported_sentence_count : int or None, optional
        Count of prose sentences lacking adequate evidence linkage.
    unsupported_sentence_ratio : float or None, optional
        Unsupported-sentence ratio over evaluated prose sentences.
    issues : list of VerificationIssue
        Detailed findings captured during verification.
    """

    model_config = ConfigDict(extra="forbid")

    stage: str
    status: str
    generated_at: str
    word_count: int | None = None
    estimated_pages: float | None = None
    quote_checks_total: int | None = None
    quote_checks_passed: int | None = None
    citation_checks_total: int | None = None
    citation_checks_passed: int | None = None
    invalid_quote_rate: float | None = None
    invalid_citation_rate: float | None = None
    prose_sentence_count: int | None = None
    unsupported_sentence_count: int | None = None
    unsupported_sentence_ratio: float | None = None
    issues: list[VerificationIssue] = Field(default_factory=list)


class FinalManifest(BaseModel):
    """Manifest describing the final promoted run artifacts.

    Attributes
    ----------
    generated_at : str
        UTC timestamp for manifest generation.
    source_hash : str or None, optional
        SHA-256 hash of the locked source text.
    config_path : str or None, optional
        Path to the config used for the run.
    output_files : list of str
        Final promoted output files.
    qa_reports : list of str
        QA and audit reports retained with the run.
    models : dict of str to str
        Logical model names used by the pipeline.
    """

    model_config = ConfigDict(extra="forbid")

    generated_at: str
    source_hash: str | None = None
    config_path: str | None = None
    output_files: list[str] = Field(default_factory=list)
    qa_reports: list[str] = Field(default_factory=list)
    models: dict[str, str] = Field(default_factory=dict)
