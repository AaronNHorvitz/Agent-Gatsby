"""Configuration models and loaders for Agent Gatsby.

This module defines the typed configuration surface used across the pipeline.
It validates the YAML configuration file, exposes frequently used path helpers,
and centralizes model and prompt resolution so individual stages can operate on
an explicit configuration object instead of re-parsing raw mappings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class PathsConfig(BaseModel):
    """Repository-relative directory layout for the pipeline.

    Attributes
    ----------
    repo_root : str
        Repository root used to resolve relative paths.
    config_dir : str
        Directory containing YAML configuration and prompt assets.
    source_dir : str
        Directory containing the locked source text.
    normalized_dir : str
        Directory containing normalized source artifacts.
    artifacts_dir : str
        Root directory for intermediate artifacts.
    manifests_dir : str
        Directory for manifests and index artifacts.
    evidence_dir : str
        Directory for extraction and evidence-ledger artifacts.
    drafts_dir : str
        Directory for English draft artifacts.
    final_dir : str
        Directory for frozen final English artifacts.
    translations_dir : str
        Directory for translated markdown artifacts.
    qa_dir : str
        Directory for QA and audit reports.
    logs_dir : str
        Directory for pipeline logs.
    outputs_dir : str
        Directory for final output files such as PDFs and manifest JSON.
    fonts_dir : str
        Directory containing local font assets for PDF rendering.
    """

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
    """Source-text normalization and manifest settings.

    Attributes
    ----------
    file_path : str
        Relative path to the locked source text.
    normalized_output_path : str
        Relative path for the normalized source output.
    manifest_output_path : str
        Relative path for the source manifest JSON.
    encoding : str, default="utf-8"
        Encoding used when decoding the locked source file.
    preserve_chapter_markers : bool, default=True
        Whether chapter markers must remain intact during normalization.
    collapse_excessive_blank_lines : bool, default=True
        Whether repeated blank lines should be collapsed during normalization.
    strip_leading_trailing_whitespace : bool, default=True
        Whether final normalized output should be trimmed.
    """

    model_config = ConfigDict(extra="forbid")

    file_path: str
    normalized_output_path: str
    manifest_output_path: str
    encoding: str = "utf-8"
    preserve_chapter_markers: bool = True
    collapse_excessive_blank_lines: bool = True
    strip_leading_trailing_whitespace: bool = True


class IndexingConfig(BaseModel):
    """Settings for passage segmentation and identifier generation.

    Attributes
    ----------
    output_path : str
        Relative path for the serialized passage index.
    chapter_pattern : str
        Regular expression used to identify chapter headings.
    paragraph_split_strategy : str
        Human-readable label describing the paragraph segmentation strategy.
    remove_empty_paragraphs : bool, default=True
        Whether empty paragraph blocks should be removed.
    passage_id_format : str, default="{chapter}.{paragraph}"
        Template used to generate stable passage identifiers.
    """

    model_config = ConfigDict(extra="forbid")

    output_path: str
    chapter_pattern: str
    paragraph_split_strategy: str
    remove_empty_paragraphs: bool = True
    passage_id_format: str = "{chapter}.{paragraph}"


class AppConfig(BaseModel):
    """Validated application configuration for the full pipeline.

    This model preserves most configuration sections as dictionaries so stages
    can evolve without a large typed-schema rewrite, while still providing
    strongly typed access to the most heavily used structural sections.

    Attributes
    ----------
    project : dict of str to Any
        Top-level project metadata.
    run : dict of str to Any
        Run-level metadata and toggles.
    paths : PathsConfig
        Repository directory layout.
    source : SourceConfig
        Source ingestion and normalization settings.
    logging : dict of str to Any
        Logging configuration.
    models : dict of str to Any
        Model names and transport-level settings.
    llm_defaults : dict of str to Any
        Default model invocation options.
    prompts : dict of str to Any
        Prompt asset locations.
    indexing : IndexingConfig
        Passage indexing settings.
    extraction : dict of str to Any
        Candidate extraction settings.
    evidence_ledger : dict of str to Any
        Evidence-ledger validation settings.
    outline : dict of str to Any
        Outline planning settings.
    drafting : dict of str to Any
        English drafting and expansion settings.
    verification : dict of str to Any
        Verification and audit settings.
    editorial : dict of str to Any
        Editorial refinement settings.
    translation : dict of str to Any
        Translation-stage settings.
    translation_outputs : dict of str to Any
        Translation output and QA artifact paths.
    translation_qa : dict of str to Any
        Translation QA configuration.
    pdf : dict of str to Any
        PDF rendering configuration.
    manifest : dict of str to Any
        Final manifest settings.
    testing : dict of str to Any
        Test-run configuration.
    orchestration : dict of str to Any
        Supported orchestration stages and stage-level configuration.
    """

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
        """Load, validate, and annotate the YAML config file.

        Parameters
        ----------
        config_path : str or Path
            Location of the YAML configuration file.

        Returns
        -------
        AppConfig
            Validated configuration model with the resolved config path cached
            for later path resolution.

        Raises
        ------
        FileNotFoundError
            If the configuration file does not exist.
        ValueError
            If the YAML cannot be parsed, does not contain a mapping, or fails
            pydantic validation.
        """

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
        """Return the resolved path to the loaded configuration file.

        Returns
        -------
        Path
            Absolute path to the YAML configuration file used to construct the
            model.
        """

        return self._config_path

    @property
    def repo_root_path(self) -> Path:
        """Return the absolute repository root for path resolution.

        Returns
        -------
        Path
            Absolute path to the repository root.
        """

        default_root = self.config_path.parent.parent
        return (default_root / self.paths.repo_root).resolve()

    def resolve_repo_path(self, value: str | Path) -> Path:
        """Resolve a repository-relative or absolute path.

        Parameters
        ----------
        value : str or Path
            Path-like value stored in the configuration.

        Returns
        -------
        Path
            Absolute path resolved against the repository root when needed.
        """

        path = Path(value)
        if path.is_absolute():
            return path
        return (self.repo_root_path / path).resolve()

    def require_mapping_value(self, section_name: str, key: str) -> Any:
        """Fetch a required value from a dictionary-backed config section.

        Parameters
        ----------
        section_name : str
            Name of the section attribute on the configuration model.
        key : str
            Required key within that section.

        Returns
        -------
        Any
            Stored configuration value.

        Raises
        ------
        ValueError
            If the section is not a mapping or the key is missing or empty.
        """

        section = getattr(self, section_name)
        if not isinstance(section, dict):
            raise ValueError(f"Config section '{section_name}' is not a mapping")
        if key not in section or section[key] in (None, ""):
            raise ValueError(f"Missing required config value: {section_name}.{key}")
        return section[key]

    @property
    def source_file_path(self) -> Path:
        """Return the absolute path to the locked source text.

        Returns
        -------
        Path
            Resolved source file path.
        """

        return self.resolve_repo_path(self.source.file_path)

    @property
    def normalized_output_path(self) -> Path:
        """Return the normalized source artifact path.

        Returns
        -------
        Path
            Resolved normalized text output path.
        """

        return self.resolve_repo_path(self.source.normalized_output_path)

    @property
    def source_manifest_path(self) -> Path:
        """Return the source manifest output path.

        Returns
        -------
        Path
            Resolved source manifest path.
        """

        return self.resolve_repo_path(self.source.manifest_output_path)

    @property
    def passage_index_path(self) -> Path:
        """Return the passage index artifact path.

        Returns
        -------
        Path
            Resolved passage index path.
        """

        return self.resolve_repo_path(self.indexing.output_path)

    @property
    def metaphor_candidates_path(self) -> Path:
        """Return the metaphor-candidate artifact path.

        Returns
        -------
        Path
            Resolved candidate output path.
        """

        return self.resolve_repo_path(self.require_mapping_value("extraction", "output_path"))

    @property
    def extraction_raw_debug_path(self) -> Path:
        """Return the extraction raw-debug output path.

        Returns
        -------
        Path
            Resolved raw extraction debug path.
        """

        return self.resolve_repo_path(self.require_mapping_value("extraction", "raw_debug_output_path"))

    @property
    def evidence_ledger_path(self) -> Path:
        """Return the evidence-ledger artifact path.

        Returns
        -------
        Path
            Resolved evidence-ledger path.
        """

        return self.resolve_repo_path(self.require_mapping_value("evidence_ledger", "output_path"))

    @property
    def rejected_candidates_path(self) -> Path:
        """Return the rejected-candidate artifact path.

        Returns
        -------
        Path
            Resolved rejected-candidate path.
        """

        return self.resolve_repo_path(self.require_mapping_value("evidence_ledger", "rejected_output_path"))

    @property
    def outline_output_path(self) -> Path:
        """Return the outline artifact path.

        Returns
        -------
        Path
            Resolved outline path.
        """

        return self.resolve_repo_path(self.require_mapping_value("outline", "output_path"))

    @property
    def draft_output_path(self) -> Path:
        """Return the English draft output path.

        Returns
        -------
        Path
            Resolved draft markdown path.
        """

        return self.resolve_repo_path(self.require_mapping_value("drafting", "output_path"))

    @property
    def final_draft_output_path(self) -> Path:
        """Return the editorial English draft output path.

        Returns
        -------
        Path
            Resolved final-draft markdown path.
        """

        return self.resolve_repo_path(self.require_mapping_value("drafting", "final_output_path"))

    @property
    def english_master_output_path(self) -> Path:
        """Return the frozen English master output path.

        Returns
        -------
        Path
            Resolved frozen English master path.
        """

        return self.resolve_repo_path(self.require_mapping_value("drafting", "master_output_path"))

    @property
    def section_drafts_dir_path(self) -> Path:
        """Return the directory that stores per-section English drafts.

        Returns
        -------
        Path
            Resolved section drafts directory.
        """

        return self.resolve_repo_path(self.require_mapping_value("drafting", "section_drafts_dir"))

    @property
    def english_verification_report_path(self) -> Path:
        """Return the English verification report path.

        Returns
        -------
        Path
            Resolved English verification report path.
        """

        return self.resolve_repo_path(self.require_mapping_value("verification", "output_path"))

    @property
    def citation_registry_output_path(self) -> Path:
        """Return the citation registry output path.

        Returns
        -------
        Path
            Resolved citation registry path.
        """

        return self.resolve_repo_path(self.require_mapping_value("verification", "citation_registry_output_path"))

    @property
    def citation_text_output_path(self) -> Path:
        """Return the rendered citation-text appendix path.

        Returns
        -------
        Path
            Resolved citation text document path.
        """

        return self.resolve_repo_path(str(self.drafting.get("citation_text_output_path", "artifacts/final/citation_text.md")))

    @property
    def spanish_translation_output_path(self) -> Path:
        """Return the Spanish translation output path.

        Returns
        -------
        Path
            Resolved Spanish translation path.
        """

        return self.resolve_repo_path(self.require_mapping_value("translation_outputs", "spanish_output_path"))

    @property
    def mandarin_translation_output_path(self) -> Path:
        """Return the Mandarin translation output path.

        Returns
        -------
        Path
            Resolved Mandarin translation path.
        """

        return self.resolve_repo_path(self.require_mapping_value("translation_outputs", "mandarin_output_path"))

    @property
    def spanish_qa_report_path(self) -> Path:
        """Return the Spanish QA report path.

        Returns
        -------
        Path
            Resolved Spanish QA report path.
        """

        return self.resolve_repo_path(self.require_mapping_value("translation_outputs", "spanish_qa_report_path"))

    @property
    def mandarin_qa_report_path(self) -> Path:
        """Return the Mandarin QA report path.

        Returns
        -------
        Path
            Resolved Mandarin QA report path.
        """

        return self.resolve_repo_path(self.require_mapping_value("translation_outputs", "mandarin_qa_report_path"))

    @property
    def english_pdf_output_path(self) -> Path:
        """Return the English PDF output path.

        Returns
        -------
        Path
            Resolved English PDF path.
        """

        return self.resolve_repo_path(self.require_mapping_value("pdf", "english_pdf_path"))

    @property
    def spanish_pdf_output_path(self) -> Path:
        """Return the Spanish PDF output path.

        Returns
        -------
        Path
            Resolved Spanish PDF path.
        """

        return self.resolve_repo_path(self.require_mapping_value("pdf", "spanish_pdf_path"))

    @property
    def mandarin_pdf_output_path(self) -> Path:
        """Return the Mandarin PDF output path.

        Returns
        -------
        Path
            Resolved Mandarin PDF path.
        """

        return self.resolve_repo_path(self.require_mapping_value("pdf", "mandarin_pdf_path"))

    @property
    def final_manifest_output_path(self) -> Path:
        """Return the final manifest output path.

        Returns
        -------
        Path
            Resolved final manifest path.
        """

        return self.resolve_repo_path(self.require_mapping_value("manifest", "output_path"))

    def resolve_prompt_path(self, prompt_key: str) -> Path:
        """Resolve a configured prompt asset path.

        Parameters
        ----------
        prompt_key : str
            Key in the ``prompts`` section of the configuration.

        Returns
        -------
        Path
            Resolved prompt file path.
        """

        return self.resolve_repo_path(self.require_mapping_value("prompts", prompt_key))

    def model_name_for(self, model_key: str) -> str:
        """Return the configured model name for a logical model key.

        Parameters
        ----------
        model_key : str
            Key in the ``models`` configuration mapping.

        Returns
        -------
        str
            Model name configured for that key.
        """

        return str(self.require_mapping_value("models", model_key))


def load_config(config_path: str | Path = "config/config.yaml") -> AppConfig:
    """Load the application configuration from disk.

    Parameters
    ----------
    config_path : str or Path, default="config/config.yaml"
        Path to the YAML config file.

    Returns
    -------
    AppConfig
        Validated application configuration.
    """

    return AppConfig.from_file(config_path)
