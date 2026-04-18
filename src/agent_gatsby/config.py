"""
Configuration loading helpers for Agent Gatsby.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_root: str
    config_dir: str
    source_dir: str
    normalized_dir: str
    artifacts_dir: str
    manifests_dir: str
    evidence_dir: str
    drafts_dir: str
    final_dir: str
    translations_dir: str
    qa_dir: str
    logs_dir: str
    outputs_dir: str
    fonts_dir: str


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    normalized_output_path: str
    manifest_output_path: str
    encoding: str = "utf-8"
    preserve_chapter_markers: bool = True
    collapse_excessive_blank_lines: bool = True
    strip_leading_trailing_whitespace: bool = True


class IndexingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_path: str
    chapter_pattern: str
    paragraph_split_strategy: str
    remove_empty_paragraphs: bool = True
    passage_id_format: str = "{chapter}.{paragraph}"


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    project: dict[str, Any] = Field(default_factory=dict)
    run: dict[str, Any] = Field(default_factory=dict)
    paths: PathsConfig
    source: SourceConfig
    logging: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
    llm_defaults: dict[str, Any] = Field(default_factory=dict)
    prompts: dict[str, Any] = Field(default_factory=dict)
    indexing: IndexingConfig
    extraction: dict[str, Any] = Field(default_factory=dict)
    evidence_ledger: dict[str, Any] = Field(default_factory=dict)
    outline: dict[str, Any] = Field(default_factory=dict)
    drafting: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    editorial: dict[str, Any] = Field(default_factory=dict)
    translation: dict[str, Any] = Field(default_factory=dict)
    translation_outputs: dict[str, Any] = Field(default_factory=dict)
    translation_qa: dict[str, Any] = Field(default_factory=dict)
    pdf: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    testing: dict[str, Any] = Field(default_factory=dict)
    orchestration: dict[str, Any] = Field(default_factory=dict)

    _config_path: Path = PrivateAttr()

    @classmethod
    def from_file(cls, config_path: str | Path) -> "AppConfig":
        path = Path(config_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML config at {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping config at {path}, got {type(data).__name__}")

        try:
            config = cls.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Config validation failed for {path}: {exc}") from exc

        config._config_path = path
        return config

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def repo_root_path(self) -> Path:
        default_root = self.config_path.parent.parent
        return (default_root / self.paths.repo_root).resolve()

    def resolve_repo_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.repo_root_path / path).resolve()

    @property
    def source_file_path(self) -> Path:
        return self.resolve_repo_path(self.source.file_path)

    @property
    def normalized_output_path(self) -> Path:
        return self.resolve_repo_path(self.source.normalized_output_path)

    @property
    def source_manifest_path(self) -> Path:
        return self.resolve_repo_path(self.source.manifest_output_path)

    @property
    def passage_index_path(self) -> Path:
        return self.resolve_repo_path(self.indexing.output_path)


def load_config(config_path: str | Path = "config/config.yaml") -> AppConfig:
    return AppConfig.from_file(config_path)
