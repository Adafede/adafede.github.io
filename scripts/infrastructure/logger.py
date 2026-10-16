"""Centralized logging configuration."""

from __future__ import annotations

import logging
import sys


def setup_logging(
    level: str = "INFO",
    format_string: str | None = None,
) -> None:
    """Configure logging for the entire application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string, uses default if None

    Raises:
        ValueError: If *level* is not a logging level name.
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Resolve through the level-name table rather than getattr(logging, ...):
    # an unknown name is a typo in the caller's configuration, and saying so
    # beats the AttributeError that getattr would raise from inside here.
    resolved = logging.getLevelNamesMapping().get(level.upper())
    if resolved is None:
        known = ", ".join(sorted(logging.getLevelNamesMapping()))
        msg = f"Unknown logging level {level!r}; expected one of: {known}"
        raise ValueError(msg)

    logging.basicConfig(
        level=resolved,
        format=format_string,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
