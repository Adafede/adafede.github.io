"""
Author metadata enrichment for HTML files.

Injects vectorial ORCID icons and Scholia profile links into author
information based on ORCID and Wikidata QID from _authors/*.yml and QMD metadata.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from ruamel.yaml import YAML

from yaml_utils import extract_yaml_frontmatter, load_metadata_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Official SVG assets from Scholia repository (vector, crisp)
ORCID_SVG_URL = (
    "https://raw.githubusercontent.com/WDscholia/scholia/main/"
    "scholia/app/static/images/orcid.svg"
)
SCHOLIA_SVG_URL = (
    "https://raw.githubusercontent.com/WDscholia/scholia/main/"
    "scholia/app/static/images/scholia_logo.svg"
)

# Use <img> tags to include the SVGs; these remain vectorial and scale cleanly
ORCID_IMG_TAG = (
    f'<img src="{ORCID_SVG_URL}" alt="ORCID" '
    f'style="height:1em; vertical-align:middle; margin-left:0.25em;" />'
)
SCHOLIA_IMG_TAG = (
    f'<img src="{SCHOLIA_SVG_URL}" alt="Scholia" '
    f'style="height:1em; vertical-align:middle; margin-left:0.25em;" />'
)


# ============================================================================
# YAML PROCESSING
# ============================================================================


def _parse_author_metadata_from_doc(doc: dict) -> List[Dict[str, str]]:
    """Parse author metadata from a YAML document.

    Accepts both 'author' (singular) and 'authors' (plural) forms.
    Returns list of author metadata dicts, preserving all fields.
    """
    if not doc or not isinstance(doc, dict):
        return []

    authors_data = []

    # Accept either 'author' (singular) or 'authors' (plural) fields.
    author_field = doc.get("author")
    if author_field is None:
        author_field = doc.get("authors", [])

    # Handle single-author dict -> list normalization
    if isinstance(author_field, dict):
        author_field = [author_field]
    elif not isinstance(author_field, list):
        return []

    for author in author_field:
        if not isinstance(author, dict):
            continue

        # Start with a copy of all author fields
        author_info = author.copy()

        # Normalize name field; prefer literal if present
        name = author.get("name")
        computed_name: Optional[str] = None
        if isinstance(name, dict):
            # Prefer explicit literal form
            literal = name.get("literal")
            if isinstance(literal, str) and literal.strip():
                computed_name = literal.strip()
            else:
                given = name.get("given", "")
                family = name.get("family", "")
                computed_name = f"{given} {family}".strip()
        elif isinstance(name, str):
            computed_name = name.strip()

        # Skip if no valid name
        if not computed_name:
            continue

        # Store computed name alongside original
        author_info["_computed_name"] = computed_name

        authors_data.append(author_info)

    return authors_data


def extract_author_metadata(qmd_path: Path) -> List[Dict[str, str]]:
    """Extract author metadata from metadata-files referenced in QMD frontmatter.

    Precedence: metadata-files (in order) -> QMD frontmatter (QMD overrides).
    Authors are merged by id or _computed_name.

    Args:
        qmd_path: Path to QMD file

    Returns:
        List of dictionaries with author info (name, orcid, qid, etc.)
    """
    authors_by_key: Dict[str, Dict[str, str]] = {}

    def merge_authors(new_authors: List[Dict[str, str]]) -> None:
        for author in new_authors:
            key = author.get("id") or author.get("_computed_name")
            if not key:
                continue
            if key in authors_by_key:
                authors_by_key[key].update(author)
            else:
                authors_by_key[key] = author.copy()

    # 1. Load from metadata-files listed in QMD frontmatter
    try:
        qmd_content = qmd_path.read_text(encoding="utf-8")
        yaml_str = extract_yaml_frontmatter(qmd_content)
        if yaml_str:
            yaml_loader = YAML(typ="safe")
            try:
                qmd_doc = yaml_loader.load(yaml_str) or {}

                # Load all metadata-files referenced in the frontmatter
                metadata_files = qmd_doc.get("metadata-files", [])
                if isinstance(metadata_files, list):
                    for metadata_path in metadata_files:
                        metadata_doc = load_metadata_file(
                            metadata_path,
                            qmd_path.parent,
                        )
                        if metadata_doc:
                            file_authors = _parse_author_metadata_from_doc(metadata_doc)
                            merge_authors(file_authors)

                # Then apply any author data from QMD frontmatter itself (overrides)
                qmd_authors = _parse_author_metadata_from_doc(qmd_doc)
                merge_authors(qmd_authors)
            except Exception as e:
                logger.warning(f"Failed to parse YAML in {qmd_path}: {e}")
    except Exception as e:
        logger.warning(f"Failed to read {qmd_path}: {e}")

    authors_data = list(authors_by_key.values())
    logger.debug(f"Extracted {len(authors_data)} authors for {qmd_path.name}")
    return authors_data


# ============================================================================
# HTML PROCESSING
# ============================================================================


def find_author_elements(soup: BeautifulSoup) -> List:
    """Find author-related elements in HTML."""
    author_elements = []
    author_elements.extend(soup.find_all(class_="author"))
    author_elements.extend(soup.find_all(class_="quarto-title-author-name"))
    author_elements.extend(soup.find_all(class_="author-meta"))
    return author_elements


def _remove_existing_orcid_icons(author_elem) -> None:
    """Remove any existing ORCID icon elements."""
    for tag in author_elem.find_all("i"):
        classes = tag.get("class", [])
        if (
            any(cls.startswith("ai") for cls in classes)
            or "orcid" in " ".join(classes).lower()
        ):
            tag.decompose()
    for svg in author_elem.find_all("svg"):
        if svg.get("aria-label") and "orcid" in svg.get("aria-label").lower():
            svg.decompose()
    for img in author_elem.find_all("img"):
        src = (img.get("src") or "").lower()
        alt = (img.get("alt") or "").lower()
        if "orcid" in src or "orcid" in alt:
            img.decompose()


def inject_orcid_icon(soup: BeautifulSoup, orcid: str, author_elem) -> bool:
    """Inject vectorial ORCID icon next to author name using official SVG."""
    _remove_existing_orcid_icons(author_elem)

    existing_link = author_elem.find("a", href=lambda h: h and "orcid.org" in h)

    if existing_link:
        for child_img in existing_link.find_all("img"):
            child_img.decompose()
        for child_i in existing_link.find_all("i"):
            child_i.decompose()
        existing_link.append(BeautifulSoup(ORCID_IMG_TAG, "html.parser"))
        existing_link["class"] = (existing_link.get("class") or []) + ["orcid-link"]
        existing_link["target"] = "_blank"
        existing_link["rel"] = "noopener noreferrer"
        existing_link["title"] = f"ORCID: {orcid}"
        href = existing_link.get("href", "")
        if not href.endswith(orcid):
            existing_link["href"] = f"https://orcid.org/{orcid}"
        logger.debug(f"Normalized existing ORCID link for {orcid}")
        return True

    text = author_elem.get_text(" ")
    orcid_re = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", re.IGNORECASE)
    if orcid_re.search(text):
        orcid_url = f"https://orcid.org/{orcid}"
        orcid_link = soup.new_tag(
            "a",
            href=orcid_url,
            **{
                "class": "orcid-link",
                "target": "_blank",
                "rel": "noopener noreferrer",
                "title": f"ORCID: {orcid}",
            },
        )
        orcid_link.append(BeautifulSoup(ORCID_IMG_TAG, "html.parser"))
        author_elem.append(orcid_link)
        logger.debug(f"Added ORCID icon (from detected text) for {orcid}")
        return True

    orcid_url = f"https://orcid.org/{orcid}"
    orcid_link = soup.new_tag(
        "a",
        href=orcid_url,
        **{
            "class": "orcid-link",
            "target": "_blank",
            "rel": "noopener noreferrer",
            "title": f"ORCID: {orcid}",
        },
    )
    orcid_link.append(BeautifulSoup(ORCID_IMG_TAG, "html.parser"))
    author_elem.append(orcid_link)
    logger.debug(f"Added ORCID icon for {orcid}")
    return True


def inject_scholia_link(soup: BeautifulSoup, qid: str, author_elem) -> bool:
    """Inject Scholia profile link next to author name using official SVG."""
    existing_link = author_elem.find(
        "a",
        href=lambda h: h and "scholia.toolforge.org" in h,
    )
    if existing_link:
        logger.debug(f"Scholia link already exists for {qid}")
        return False

    scholia_url = f"https://scholia.toolforge.org/author/{qid}"
    scholia_link = soup.new_tag(
        "a",
        href=scholia_url,
        **{
            "class": "scholia-link",
            "target": "_blank",
            "rel": "noopener noreferrer",
            "title": f"Scholia profile: {qid}",
        },
    )
    scholia_link.append(BeautifulSoup(SCHOLIA_IMG_TAG, "html.parser"))
    author_elem.append(scholia_link)
    logger.debug(f"Added Scholia link for {qid}")
    return True


def enrich_authors_in_html(
    soup: BeautifulSoup,
    authors_metadata: List[Dict[str, str]],
) -> int:
    """Enrich author elements with ORCID and Scholia links."""
    if not authors_metadata:
        logger.debug("No author metadata to inject")
        return 0

    author_elements = find_author_elements(soup)
    if not author_elements:
        logger.debug("No author elements found in HTML")
        return 0

    enriched_count = 0

    for author_meta in authors_metadata:
        author_name = author_meta.get("_computed_name")
        if not author_name:
            name = author_meta.get("name")
            if isinstance(name, str):
                author_name = name
            elif isinstance(name, dict):
                given = name.get("given", "")
                family = name.get("family", "")
                author_name = f"{given} {family}".strip()

        if not author_name:
            continue

        for author_elem in author_elements:
            elem_text = author_elem.get_text().strip()
            if author_name in elem_text or elem_text in author_name or elem_text == "":
                if elem_text == "":
                    author_elem.insert(0, author_name)

                if "orcid" in author_meta:
                    if inject_orcid_icon(soup, author_meta["orcid"], author_elem):
                        enriched_count += 1

                if "qid" in author_meta:
                    if inject_scholia_link(soup, author_meta["qid"], author_elem):
                        enriched_count += 1

                break

    return enriched_count


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def inject_author_links(qmd_path: Path, html_path: Path) -> None:
    """Inject ORCID and Scholia links into HTML based on QMD metadata."""
    qmd_path = Path(qmd_path)
    html_path = Path(html_path)

    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    authors_metadata = extract_author_metadata(qmd_path)
    if not authors_metadata:
        logger.debug(f"No author metadata found in {qmd_path.name}")
        return

    try:
        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.error(f"Failed to read HTML {html_path}: {e}")
        return

    enriched_count = enrich_authors_in_html(soup, authors_metadata)

    if enriched_count > 0:
        try:
            html_path.write_text(str(soup), encoding="utf-8")
            logger.info(
                f"✓ Enriched {enriched_count} author elements in {html_path.name}",
            )
        except Exception as e:
            logger.error(f"Failed to write HTML {html_path}: {e}")
    else:
        logger.debug(f"No author enrichment for {html_path.name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: inject_author_links.py <qmd_file> <html_file>")
        print()
        print("Example:")
        print("  inject_author_links.py talks/my-talk.qmd _site/talks/my-talk.html")
        sys.exit(1)

    inject_author_links(Path(sys.argv[1]), Path(sys.argv[2]))
