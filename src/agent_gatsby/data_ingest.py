"""Source ingestion and source-manifest generation.

This module owns the earliest file-system interaction in the pipeline. It reads
the locked source text, validates that it is present and non-empty, computes a
stable SHA-256 digest, and writes a manifest that downstream stages use for
auditability and reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from agent_gatsby.config import AppConfig
from agent_gatsby.schemas import SourceManifest

LOGGER = logging.getLogger(__name__)


def utc_now_iso() -> str:
    """Return the current UTC timestamp in canonical manifest format.

    Returns
    -------
    str
        ISO-8601 timestamp with a trailing ``Z`` suffix.
    """

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_sha256(data: bytes) -> str:
    """Compute a SHA-256 digest for a byte payload.

    Parameters
    ----------
    data : bytes
        Raw bytes to hash.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """

    return hashlib.sha256(data).hexdigest()


def read_source_bytes(config: AppConfig) -> bytes:
    """Read the locked source file from disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    bytes
        Raw source file bytes.

    Raises
    ------
    FileNotFoundError
        If the configured source file does not exist.
    ValueError
        If the file exists but contains only whitespace.
    """

    source_path = config.source_file_path
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    LOGGER.info("Reading source text from %s", source_path)
    data = source_path.read_bytes()
    if not data.strip():
        raise ValueError(f"Source file is empty: {source_path}")
    LOGGER.info("Read %d bytes from source text", len(data))
    return data


def decode_source_text(source_bytes: bytes, encoding: str) -> str:
    """Decode raw source bytes into text.

    Parameters
    ----------
    source_bytes : bytes
        Raw bytes read from the source file.
    encoding : str
        Text encoding used to decode the bytes.

    Returns
    -------
    str
        Decoded source text.

    Raises
    ------
    ValueError
        If the decoded text is empty after stripping whitespace.
    UnicodeDecodeError
        If decoding fails for the supplied encoding.
    """

    text = source_bytes.decode(encoding)
    if not text.strip():
        raise ValueError("Decoded source text is empty after stripping whitespace")
    return text


def build_source_manifest(config: AppConfig, source_bytes: bytes) -> SourceManifest:
    """Construct the source manifest for the current run.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    source_bytes : bytes
        Raw locked-source bytes.

    Returns
    -------
    SourceManifest
        Manifest describing the locked source input.
    """

    return SourceManifest(
        source_name=config.normalized_output_path.stem,
        source_path=config.source.file_path,
        encoding=config.source.encoding,
        sha256=compute_sha256(source_bytes),
        file_size_bytes=len(source_bytes),
        generated_at=utc_now_iso(),
        normalized_output_path=config.source.normalized_output_path,
    )


def write_source_manifest(config: AppConfig, manifest: SourceManifest) -> None:
    """Write the source manifest to disk.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.
    manifest : SourceManifest
        Manifest payload to serialize.

    Returns
    -------
    None
        The manifest is written to the configured artifact path.
    """

    output_path = config.source_manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote source manifest to %s", output_path)


def ingest_source(config: AppConfig) -> tuple[str, SourceManifest]:
    """Read, decode, hash, and persist source metadata for the run.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    tuple of (str, SourceManifest)
        Decoded source text and the generated source manifest.
    """

    source_bytes = read_source_bytes(config)
    source_text = decode_source_text(source_bytes, config.source.encoding)
    manifest = build_source_manifest(config, source_bytes)
    LOGGER.info("Computed source SHA-256: %s", manifest.sha256)
    write_source_manifest(config, manifest)
    return source_text, manifest
