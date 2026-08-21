"""Characterization tests for MetadataService (QMD frontmatter updates).

Captures behavior of date-from-filename stamping and DOI generation so
that refactors of the pre-render hook cannot drift.
"""

from pathlib import Path

import pytest

from scripts.infrastructure import FileSystem
from scripts.services.metadata_service import MetadataService


@pytest.fixture()
def fs(tmp_path: Path) -> FileSystem:
    return FileSystem(tmp_path)


@pytest.fixture()
def metadata_service(fs: FileSystem) -> MetadataService:
    return MetadataService(fs)


def _frontmatter_text(text: str) -> str:
    """Extract just the frontmatter block as raw text (no YAML parsing)."""
    lines = text.splitlines()
    end = 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    return "\n".join(lines[1:end])


def test_date_extracted_from_filename(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """A post without ``date`` in frontmatter gets it from its filename prefix."""
    qmd = tmp_path / "2025-08-04_rogue_scholar.qmd"
    qmd.write_text("---\ntitle: Test Post\n---\n\nHello.\n", encoding="utf-8")

    changed = metadata_service.update_post_metadata(qmd, generate_doi=False)

    assert changed is True
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "date: 2025-08-04" in fm


def test_doi_generated_when_missing(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """A post without a DOI gets one generated (prefix 10.59350)."""
    qmd = tmp_path / "2025-01-01_test.qmd"
    qmd.write_text(
        "---\ntitle: No DOI Yet\ndate: 2025-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    changed = metadata_service.update_post_metadata(qmd, generate_doi=True)

    assert changed is True
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "doi:" in fm
    assert "10.59350/" in fm


def test_existing_doi_not_overwritten(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """A post that already has a DOI does not get it regenerated."""
    qmd = tmp_path / "2025-01-01_test.qmd"
    qmd.write_text(
        "---\ntitle: Has DOI\ndate: 2025-01-01\ndoi: 10.59350/existing-123\n---\n\nBody.\n",
        encoding="utf-8",
    )

    changed = metadata_service.update_post_metadata(qmd, generate_doi=True)

    # Date matches filename, DOI already exists → no changes needed
    assert changed is False
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "10.59350/existing-123" in fm


def test_date_mismatch_corrected(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """A wrong date in frontmatter is overwritten with the filename date."""
    qmd = tmp_path / "2025-03-15_test.qmd"
    qmd.write_text(
        "---\ntitle: Wrong Date\ndate: 2099-12-31\n---\n\nBody.\n",
        encoding="utf-8",
    )

    changed = metadata_service.update_post_metadata(qmd, generate_doi=False)

    assert changed is True
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "date: 2025-03-15" in fm
    assert "2099-12-31" not in fm


def test_doi_not_generated_when_generate_doi_false_but_date_updated(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """With generate_doi=False, date is still updated if mismatched, but no DOI added."""
    qmd = tmp_path / "2025-06-01_test.qmd"
    qmd.write_text(
        "---\ntitle: No DOI\ndate: 2000-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    changed = metadata_service.update_post_metadata(qmd, generate_doi=False)

    assert changed is True
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "date: 2025-06-01" in fm
    assert "doi:" not in fm


def test_unmodified_post_not_rewritten(
    tmp_path: Path,
    fs: FileSystem,
    metadata_service: MetadataService,
):
    """If date and DOI already match, the file is not touched."""
    qmd = tmp_path / "2025-01-01_test.qmd"
    original = (
        "---\ntitle: Fine\ndate: 2025-01-01\ndoi: 10.59350/existing\n---\n\nBody.\n"
    )
    qmd.write_text(original, encoding="utf-8")

    changed = metadata_service.update_post_metadata(qmd, generate_doi=True)

    # Date matches filename, DOI already exists → no changes needed
    assert changed is False
    fm = _frontmatter_text(qmd.read_text(encoding="utf-8"))
    assert "date: 2025-01-01" in fm
    assert "doi: 10.59350/existing" in fm
