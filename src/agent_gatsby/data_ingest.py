"""
Source ingestion and manifest writing for Agent Gatsby.
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
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_source_bytes(config: AppConfig) -> bytes:
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
    text = source_bytes.decode(encoding)
    if not text.strip():
        raise ValueError("Decoded source text is empty after stripping whitespace")
    return text


def build_source_manifest(config: AppConfig, source_bytes: bytes) -> SourceManifest:
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
    output_path = config.source_manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.model_dump(exclude_none=True), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    LOGGER.info("Wrote source manifest to %s", output_path)


def ingest_source(config: AppConfig) -> tuple[str, SourceManifest]:
    source_bytes = read_source_bytes(config)
    source_text = decode_source_text(source_bytes, config.source.encoding)
    manifest = build_source_manifest(config, source_bytes)
    LOGGER.info("Computed source SHA-256: %s", manifest.sha256)
    write_source_manifest(config, manifest)
    return source_text, manifest
