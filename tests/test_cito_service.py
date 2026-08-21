"""Characterization tests for CitoService (CiTO citation parsing & injection).

These tests capture the *current* observable behavior so that refactors
do not silently change the injected annotation output.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scripts.infrastructure import FileSystem
from scripts.services.cito_service import CitoService


@pytest.fixture()
def fs(tmp_path: Path) -> FileSystem:
    return FileSystem(tmp_path)


@pytest.fixture()
def cito(fs: FileSystem) -> CitoService:
    from scripts.infrastructure import HtmlProcessor

    return CitoService(fs, HtmlProcessor())


# ---------------------------------------------------------------------------
# parse_citations_from_qmd
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_single_citation_with_property(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    """``[@cites:smith2020]`` yields cite_id ``smith2020`` with property ``cites``."""
    qmd = _write(tmp_path / "post.qmd", "Some text [@cites:smith2020] more.\n")
    result = cito.parse_citations_from_qmd(qmd)
    assert result == {"smith2020": {"cites"}}


def test_parse_multiple_citations_in_one_bracket(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    """Semicolon-separated citations inside one ``[@...]`` are parsed separately."""
    qmd = _write(tmp_path / "post.qmd", "[@cites:smith2020; supports:jones2021]\n")
    result = cito.parse_citations_from_qmd(qmd)
    assert result == {
        "smith2020": {"cites"},
        "jones2021": {"supports"},
    }


def test_parse_citation_without_property_defaults_to_citation(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    """``[@smith2020]`` (no ``property:`` prefix) defaults to property ``citation``."""
    qmd = _write(tmp_path / "post.qmd", "Text [@smith2020] end.\n")
    result = cito.parse_citations_from_qmd(qmd)
    assert result == {"smith2020": {"citation"}}


def test_parse_citation_ids_merge_properties(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    """The same cite_id appearing in two brackets merges its property sets."""
    qmd = _write(
        tmp_path / "post.qmd",
        "Text [@cites:smith2020; supports:smith2020] end.\n",
    )
    result = cito.parse_citations_from_qmd(qmd)
    assert result == {"smith2020": {"cites", "supports"}}


def test_parse_citation_strips_whitespace(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    """Leading/trailing whitespace around property and id is stripped."""
    qmd = _write(tmp_path / "post.qmd", "[@  cites :  smith2020  ]\n")
    result = cito.parse_citations_from_qmd(qmd)
    assert result == {"smith2020": {"cites"}}


def test_parse_missing_file_returns_empty(
    tmp_path: Path,
    fs: FileSystem,
    cito: CitoService,
):
    result = cito.parse_citations_from_qmd(tmp_path / "nonexistent.qmd")
    assert result == {}


# ---------------------------------------------------------------------------
# inject_into_html
# ---------------------------------------------------------------------------


def _sample_html_with_refs(citations: dict[str, set[str]]) -> str:
    """Render a minimal bibliography block mirroring Pandoc/Quarto output."""
    entries = []
    for cite_id in citations:
        entries.append(
            f'<div id="ref-{cite_id}" class="csl-entry">Some citation.</div>',
        )
    return '<div id="refs">\n' + "\n".join(entries) + "\n</div>"


def test_inject_single_citation(tmp_path: Path, cito: CitoService):
    html = _sample_html_with_refs({"smith2020": {"cites"}})
    html_file = _write(tmp_path / "out.html", f"<html><body>{html}</body></html>")

    changed = cito.inject_into_html(html_file, {"smith2020": ["cites"]})

    assert changed is True
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    entry = soup.find("div", id="ref-smith2020")
    cito_span = entry.find("span", class_="cito")
    assert cito_span is not None
    assert "cito:cites" in cito_span.text


def test_inject_multiple_properties_are_camelcased(tmp_path: Path, cito: CitoService):
    html_file = _write(
        tmp_path / "out.html",
        '<html><body><div id="refs">'
        '<div id="ref-doe2023" class="csl-entry">Doe.</div>'
        "</div></body></html>",
    )

    changed = cito.inject_into_html(
        html_file,
        {"doe2023": ["cites_as_evidence", "supports"]},
    )

    assert changed is True
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    span = soup.find("span", class_="cito")
    assert span is not None
    assert "[cito:citesAsEvidence]" in span.text
    assert "[cito:supports]" in span.text


def test_inject_skips_entries_without_cito_properties(
    tmp_path: Path,
    cito: CitoService,
):
    html_file = _write(
        tmp_path / "out.html",
        '<html><body><div id="refs">'
        '<div id="ref-alpha" class="csl-entry">Alpha.</div>'
        '<div id="ref-beta" class="csl-entry">Beta.</div>'
        "</div></body></html>",
    )

    changed = cito.inject_into_html(html_file, {"beta": ["cites"]})

    assert changed is True
    soup = BeautifulSoup(html_file.read_text(encoding="utf-8"), "html.parser")
    alpha = soup.find("div", id="ref-alpha")
    beta = soup.find("div", id="ref-beta")
    assert alpha.find("span", class_="cito") is None
    assert beta.find("span", class_="cito") is not None


def test_inject_is_idempotent(tmp_path: Path, cito: CitoService):
    """Re-running inject on already-annotated HTML does not add another span."""
    html_file = _write(
        tmp_path / "out.html",
        '<html><body><div id="refs">'
        '<div id="ref-x" class="csl-entry">X.'
        '<span class="cito"> [cito:cites]</span></div>'
        "</div></body></html>",
    )

    changed = cito.inject_into_html(html_file, {"x": ["cites"]})

    assert changed is False  # nothing new added


def test_inject_no_refs_container_returns_false(tmp_path: Path, cito: CitoService):
    html_file = _write(
        tmp_path / "out.html",
        "<html><body><p>No refs here.</p></body></html>",
    )

    changed = cito.inject_into_html(html_file, {"x": ["cites"]})

    assert changed is False
