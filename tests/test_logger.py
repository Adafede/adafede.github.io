"""Logging configuration."""

import logging

import pytest

from scripts.infrastructure.logger import setup_logging


def test_an_unknown_level_names_the_ones_that_exist():
    """A typo in a caller's level used to surface as an AttributeError from
    inside logging's namespace, which says nothing about what went wrong."""
    with pytest.raises(ValueError, match="Unknown logging level 'LOUD'"):
        setup_logging(level="LOUD")


def test_a_known_level_is_applied():
    setup_logging(level="debug")
    try:
        assert logging.getLogger().level == logging.DEBUG
    finally:
        setup_logging(level="INFO")
