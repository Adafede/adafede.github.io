"""
DOI injector for RSS feeds.

Extracts DOIs from QMD file metadata and injects them into corresponding
RSS feed items. Uses the refactored infrastructure layer.
"""

import sys
from pathlib import Path
from typing import Dict, List, Union

from bs4 import BeautifulSoup

# Add parent directory to path for infrastructure imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure import YamlLoader, get_logger

logger = get_logger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

DOI_URL_PREFIX = "https://doi.org/"


# ============================================================================
# DOI EXTRACTION
# ============================================================================


def extract_doi_from_qmd(qmd_path: Path, yaml_loader: YamlLoader) -> Dict[str, str]:
    """Extract title and DOI from QMD file metadata.

    Args:
        qmd_path: Path to QMD file
        yaml_loader: YamlLoader instance

    Returns:
        Dictionary with title and DOI, or empty dict if not found
    """
    try:
        metadata = yaml_loader.load_from_path(qmd_path)
    except Exception as e:
        logger.warning(f"Failed to load metadata from {qmd_path}: {e}")
        return {}

    if not metadata:
        return {}

    title = metadata.get("title")
    doi = metadata.get("doi")

    if not (title and doi):
        return {}

    # Normalize DOI to full URL
    doi = doi.strip()
    if not doi.startswith("http"):
        doi = DOI_URL_PREFIX + doi

    return {"title": title.strip(), "doi": doi}


def build_doi_mapping(
    qmd_files: List[Union[str, Path]],
    yaml_loader: YamlLoader,
) -> Dict[str, str]:
    """Build mapping from titles to DOIs from QMD files.

    Args:
        qmd_files: List of QMD file paths
        yaml_loader: YamlLoader instance

    Returns:
        Dictionary mapping titles to DOI URLs
    """
    doi_mapping = {}

    for qmd_file in qmd_files:
        qmd_path = Path(qmd_file)
        result = extract_doi_from_qmd(qmd_path, yaml_loader)
        if result:
            doi_mapping[result["title"]] = result["doi"]

    logger.info(f"Extracted DOIs for {len(doi_mapping)} articles")
    return doi_mapping


# ============================================================================
# RSS PROCESSING
# ============================================================================


def inject_doi_in_rss(
    rss_path: Path,
    qmd_files: List[Union[str, Path]],
    yaml_loader: YamlLoader = None,
) -> None:
    """Inject DOIs into RSS feed items.

    Args:
        rss_path: Path to RSS XML file
        qmd_files: List of QMD file paths to extract DOIs from
        yaml_loader: YamlLoader instance (creates new one if not provided)

    Example:
        >>> yaml_loader = YamlLoader()
        >>> inject_doi_in_rss(Path('posts.xml'), [Path('posts/my-post.qmd')], yaml_loader)
    """
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
    except Exception as e:
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
        except Exception as e:
            logger.error(f"Failed to write RSS {rss_path}: {e}")
    else:
        logger.debug(f"No DOIs added to {rss_path.name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: inject_doi_in_rss.py <rss_file> <qmd_file1> [qmd_file2 ...]")
        sys.exit(1)

    inject_doi_in_rss(Path(sys.argv[1]), sys.argv[2:])
