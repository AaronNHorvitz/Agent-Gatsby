"""
Logging helpers for Agent Gatsby.
"""

from __future__ import annotations

import logging

from agent_gatsby.config import AppConfig


def build_log_formatter(config: AppConfig) -> logging.Formatter:
    logging_config = config.logging
    parts: list[str] = []

    if logging_config.get("include_timestamps", True):
        parts.append("%(asctime)s")
    parts.append("%(levelname)s")
    if logging_config.get("include_stage_names", True):
        parts.append("%(name)s")
    parts.append("%(message)s")

    return logging.Formatter(" | ".join(parts))


def configure_logging(config: AppConfig) -> None:
    logging_config = config.logging
    level_name = str(logging_config.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = build_log_formatter(config)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(level)

    if logging_config.get("log_to_console", True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if logging_config.get("log_to_file", False):
        file_path = config.resolve_repo_path(logging_config.get("file_path", "artifacts/logs/pipeline.log"))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

