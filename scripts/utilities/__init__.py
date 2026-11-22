"""Utility scripts for post-processing."""

from __future__ import annotations

import importlib
import sys
import types
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

_EXPORTS = frozenset(__all__)


class _UtilitiesModule(types.ModuleType):
    """Package module whose lazy callable exports are not shadowed by submodules."""

    def __setattr__(self, name: str, value: object) -> None:
        """Bind the exported callable when Python attaches a same-named submodule."""
        if (
            name in _EXPORTS
            and isinstance(value, types.ModuleType)
            and value.__name__ == f"{self.__name__}.{name}"
        ):
            value = getattr(value, name)
        super().__setattr__(name, value)


def __getattr__(name: str) -> object:
    """Lazily import utility callables so heavy optional plots load on demand."""
    if name in _EXPORTS:
        module = importlib.import_module(f".{name}", __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Include lazy exports in ``dir(scripts.utilities)``."""
    return sorted({*globals(), *__all__})


sys.modules[__name__].__class__ = _UtilitiesModule
