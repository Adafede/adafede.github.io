"""Utility scripts for post-processing."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .convert_rss_to_json_feed import convert_rss_to_json_feed
    from .enforce_website_spec import enforce_website_spec
    from .fix_accessibility import fix_accessibility
    from .inject_cito_annotations_in_rss import inject_cito_annotations_in_rss
    from .inject_doi_in_rss import inject_doi_in_rss
    from .process_qmd_directory import process_qmd_directory
    from .render_circle_packing import render_circle_packing
    from .run_pandoc_for_all_qmds import run_pandoc_for_all_qmds
    from .talkmap import talkmap

__all__ = [
    "convert_rss_to_json_feed",
    "enforce_website_spec",
    "fix_accessibility",
    "inject_cito_annotations_in_rss",
    "inject_doi_in_rss",
    "process_qmd_directory",
    "render_circle_packing",
    "run_pandoc_for_all_qmds",
    "talkmap",
]


def __getattr__(name: str) -> object:
    """Lazily import utility callables so heavy optional plots load on demand."""
    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
