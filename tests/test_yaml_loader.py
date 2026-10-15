"""YAML loader degradation on malformed input."""

from pathlib import Path

import pytest

from scripts.infrastructure.yaml_loader import YamlLoader


@pytest.fixture()
def loader() -> YamlLoader:
    return YamlLoader()


def test_malformed_frontmatter_returns_none_instead_of_raising(
    tmp_path: Path,
    loader: YamlLoader,
):
    """Both loaders promise None for invalid YAML.

    ruamel raises MarkedYAMLError, which is not a ValueError, so a single
    malformed .qmd used to abort the whole pre-render run.
    """
    broken = tmp_path / "2024-01-01_broken.qmd"
    broken.write_text("---\ntitle: [unclosed\n---\nbody\n", encoding="utf-8")

    assert loader.load_from_path(broken) is None


def test_malformed_string_returns_none_instead_of_raising(
    loader: YamlLoader,
):
    assert loader.load_from_string("title: [unclosed") is None


def test_valid_yaml_still_loads(loader: YamlLoader):
    assert loader.load_from_string("title: Fine\ntags: [a, b]") == {
        "title": "Fine",
        "tags": ["a", "b"],
    }
