"""
Structured artifact schemas for the early Agent Gatsby pipeline stages.
"""

from __future__ import annotations

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

