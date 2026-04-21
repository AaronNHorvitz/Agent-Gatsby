"""Logging configuration helpers for Agent Gatsby.

This module centralizes console and file logging setup for the pipeline. It
rebuilds the root logger from configuration on each run so stage execution and
artifact-writing events are emitted consistently in both interactive and batch
contexts.
"""

from __future__ import annotations

import logging

from agent_gatsby.config import AppConfig


def build_log_formatter(config: AppConfig) -> logging.Formatter:
    """Build the configured log-line formatter.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    logging.Formatter
        Formatter configured according to timestamp and stage-name settings.
    """

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
    """Configure the root logger for the current pipeline run.

    Parameters
    ----------
    config : AppConfig
        Validated application configuration.

    Returns
    -------
    None
        This function mutates the root logger in place.

    Notes
    -----
    Existing handlers are removed and closed before new handlers are attached
    so repeated stage runs do not duplicate log output.
    """

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
