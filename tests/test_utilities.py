"""Lazy export behavior for ``scripts.utilities``."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.utilities

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_in_fresh_python(code: str) -> None:
    """Execute *code* in an isolated Python process anchored at the project root."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def test_every_exported_utility_imports_as_callable() -> None:
    """Each ``__all__`` export must resolve to its callable, never its submodule."""
    _run_in_fresh_python(
        """
import sys
import types
import scripts.utilities as utilities

for name in utilities.__all__:
    namespace: dict[str, object] = {}
    exec(f"from scripts.utilities import {name}", namespace)
    exported = namespace[name]
    submodule = sys.modules[f"scripts.utilities.{name}"]
    assert callable(exported), f"{name} is not callable: {exported!r}"
    assert not isinstance(exported, types.ModuleType), (
        f"{name} resolved to module {exported!r}"
    )
    assert exported is getattr(submodule, name)
""",
    )


def test_utilities_package_loads_submodules_lazily() -> None:
    """Importing one lightweight helper must not eagerly load plotting modules."""
    _run_in_fresh_python(
        """
import sys
import scripts.utilities
from scripts.utilities import enforce_website_spec

assert callable(enforce_website_spec)
assert "scripts.utilities.render_circle_packing" not in sys.modules
assert "scripts.utilities.talkmap" not in sys.modules
""",
    )


def test_submodule_import_before_package_import_does_not_shadow_callable() -> None:
    """Importing a submodule attribute in either order must keep the callable export."""
    _run_in_fresh_python(
        """
import sys
import types
from scripts.utilities.talkmap import GeoCache
from scripts.utilities import talkmap

assert GeoCache is not None
assert callable(talkmap)
assert not isinstance(talkmap, types.ModuleType)
assert talkmap is sys.modules["scripts.utilities.talkmap"].talkmap
""",
    )
    _run_in_fresh_python(
        """
import sys
import types
import scripts.utilities as utilities
from scripts.utilities import talkmap
from scripts.utilities.talkmap import create_popup_html

assert callable(create_popup_html)
assert callable(talkmap)
assert callable(utilities.talkmap)
assert not isinstance(utilities.talkmap, types.ModuleType)
assert talkmap is sys.modules["scripts.utilities.talkmap"].talkmap
""",
    )


def test_postrender_binds_utility_callables_without_loading_plot_modules() -> None:
    """``scripts.postrender`` must bind callable utilities without loading plots."""
    _run_in_fresh_python(
        """
import sys
import types
import scripts.postrender as pr

expected = (
    "convert_rss_to_json_feed",
    "enforce_website_spec",
    "fix_accessibility",
    "inject_cito_annotations_in_rss",
    "inject_doi_in_rss",
    "process_qmd_directory",
    "run_pandoc_for_all_qmds",
)
for name in expected:
    bound = getattr(pr, name)
    assert callable(bound), f"postrender.{name} is not callable: {bound!r}"
    assert not isinstance(bound, types.ModuleType)

assert "scripts.utilities.render_circle_packing" not in sys.modules
assert "scripts.utilities.talkmap" not in sys.modules
""",
    )


def test_unknown_attribute_raises_attribute_error() -> None:
    """Accessing an unknown attribute on ``scripts.utilities`` raises AttributeError."""
    with pytest.raises(AttributeError):
        _ = scripts.utilities.does_not_exist


def test_dir_includes_all_exports() -> None:
    """``dir(scripts.utilities)`` exposes every lazy export listed in ``__all__``."""
    assert set(scripts.utilities.__all__).issubset(dir(scripts.utilities))
