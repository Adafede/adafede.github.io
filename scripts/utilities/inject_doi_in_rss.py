"""
DOI injector for RSS feeds.

Extracts DOIs from QMD file metadata and injects them into corresponding
RSS feed items. Uses the refactored infrastructure layer.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from bs4 import BeautifulSoup

# Add project root to path so `scripts` is importable as a package
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from scripts.config import DOI_URL_PREFIX
from scripts.infrastructure import YamlLoader, get_logger

logger = get_logger(__name__)


def extract_doi_from_qmd(qmd_path: Path, yaml_loader: YamlLoader) -> dict[str, str]:
    """Extract ``title`` and ``doi`` from a QMD file's YAML frontmatter.

    Returns an empty dict if either field is missing or not a string.
    """
    try:
        metadata_raw = yaml_loader.load_from_path(qmd_path)
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to load metadata from {qmd_path}: {e}")
        return {}

    if not metadata_raw or not isinstance(metadata_raw, dict):
        return {}

    metadata: dict[str, object] = metadata_raw

    title = metadata.get("title")
    doi = metadata.get("doi")

    if not (isinstance(title, str) and isinstance(doi, str)):
        return {}

    # Normalize DOI to full URL
    doi_str = doi.strip()
    if not doi_str.startswith("http"):
        doi_str = DOI_URL_PREFIX + doi_str

    return {"title": title.strip(), "doi": doi_str}


def build_doi_mapping(
    qmd_files: Sequence[str | Path],
    yaml_loader: YamlLoader,
) -> dict[str, str]:
    """Build a ``{title: doi_url}`` mapping from a list of QMD files."""
    doi_mapping = {}

    for qmd_file in qmd_files:
        qmd_path = Path(qmd_file)
        result = extract_doi_from_qmd(qmd_path, yaml_loader)
        if result:
            doi_mapping[result["title"]] = result["doi"]

    logger.info(f"Extracted DOIs for {len(doi_mapping)} articles")
    return doi_mapping


def inject_doi_in_rss(
    rss_path: Path,
    qmd_files: Sequence[str | Path],
    yaml_loader: YamlLoader | None = None,
) -> None:
    """Inject DOI tags into RSS ``<item>`` elements based on QMD metadata."""
    rss_path = Path(rss_path)

    if not rss_path.exists():
        logger.warning(f"RSS file not found: {rss_path}")
        return

    # Create yaml_loader if not provided
    if yaml_loader is None:
        yaml_loader = YamlLoader()

    # Build title -> DOI mapping
    doi_mapping = build_doi_mapping(qmd_files, yaml_loader)
    if not doi_mapping:
        logger.warning("No DOIs found in QMD files")
        return

    # Read and parse RSS
    try:
        with open(rss_path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "xml")
    except (OSError, ValueError) as e:
        logger.error(f"Failed to read RSS {rss_path}: {e}")
        return

    # Process items
    items = soup.find_all("item")
    modified = False

    for item in items:
        title_tag = item.find("title")
        if not title_tag:
            continue

        title = title_tag.text.strip()
        doi = doi_mapping.get(title)
        if not doi:
            continue

        # Only add DOI if not already present
        existing_doi = item.find("doi")
        if existing_doi:
            logger.debug(f"DOI already exists for '{title}'")
            continue

        # Create and append DOI tag
        doi_tag = soup.new_tag("doi")
        doi_tag.string = doi
        item.append(doi_tag)
        modified = True
        logger.debug(f"Added DOI for '{title}': {doi}")

    # Write back if modified
    if modified:
        try:
            with open(rss_path, "w", encoding="utf-8") as f:
                f.write(str(soup))
            logger.info(f"Injected DOIs into {rss_path.name}")
        except OSError as e:
            logger.error(f"Failed to write RSS {rss_path}: {e}")
    else:
        logger.debug(f"No DOIs added to {rss_path.name}")


if __name__ == "__main__":
    import sys
    from typing import cast

    if len(sys.argv) < 3:
        print("Usage: inject_doi_in_rss.py <rss_file> <qmd_file1> [qmd_file2 ...]")
        sys.exit(1)

    inject_doi_in_rss(Path(sys.argv[1]), cast(list[str | Path], sys.argv[2:]))
