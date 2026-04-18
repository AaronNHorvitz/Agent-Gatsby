"""
Structured artifact schemas for the early Agent Gatsby pipeline stages.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceManifest(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    passage_id: str
    chapter: int
    paragraph: int
    text: str
    char_start: int
    char_end: int


class PassageIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    normalized_path: str
    chapter_count: int
    passage_count: int
    generated_at: str
    passages: list[PassageRecord] = Field(default_factory=list)


class MetaphorCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    label: str
    passage_id: str
    quote: str
    rationale: str
    confidence: float


class RejectedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    reason: str
    passage_id: str | None = None
    label: str | None = None
    quote: str | None = None


class EvidenceRecord(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    section_id: str
    heading: str
    purpose: str
    evidence_ids: list[str] = Field(default_factory=list)


class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    passage_id: str | None = None
    evidence_id: str | None = None


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    status: str
    generated_at: str
    issues: list[VerificationIssue] = Field(default_factory=list)


class FinalManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    source_hash: str | None = None
    config_path: str | None = None
    output_files: list[str] = Field(default_factory=list)
    qa_reports: list[str] = Field(default_factory=list)
    models: dict[str, str] = Field(default_factory=dict)
