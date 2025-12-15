"""
Author metadata enrichment for HTML files.

Injects vectorial ORCID icons and Scholia profile links into author
information based on ORCID and Wikidata QID from QMD metadata.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from ruamel.yaml import YAML

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

YAML_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


# ============================================================================
# YAML PROCESSING
# ============================================================================


def extract_yaml_frontmatter(qmd_content: str) -> Optional[str]:
    """Extract YAML frontmatter from QMD content.

    Args:
        qmd_content: Content of QMD file

    Returns:
        YAML frontmatter string or None if not found
    """
    match = YAML_FRONTMATTER_PATTERN.match(qmd_content)
    return match.group(1) if match else None


def extract_author_metadata(qmd_path: Path) -> List[Dict[str, str]]:
    """Extract author metadata from QMD file.

    Args:
        qmd_path: Path to QMD file

    Returns:
        List of dictionaries with author info (name, orcid, qid)
    """
    try:
        qmd_content = qmd_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {qmd_path}: {e}")
        return []

    yaml_str = extract_yaml_frontmatter(qmd_content)
    if not yaml_str:
        logger.debug(f"No YAML frontmatter found in {qmd_path}")
        return []

    yaml_loader = YAML(typ="safe")
    try:
        metadata = yaml_loader.load(yaml_str)
    except Exception as e:
        logger.warning(f"Failed to parse YAML in {qmd_path}: {e}")
        return []

    if not metadata:
        return []

    authors_data = []
    # Accept either 'author' (singular) or 'authors' (plural) fields.
    author_field = metadata.get("author")
    if author_field is None:
        author_field = metadata.get("authors", [])

    # Handle single-author dict -> list normalization; if it's not a list or dict, bail out
    if isinstance(author_field, dict):
        author_field = [author_field]
    elif not isinstance(author_field, list):
        return []

    for author in author_field:
        if not isinstance(author, dict):
            continue

        author_info = {}

        # Extract name (can be string or dict with given/family)
        name = author.get("name")
        if isinstance(name, dict):
            given = name.get("given", "")
            family = name.get("family", "")
            author_info["name"] = f"{given} {family}".strip()
        elif isinstance(name, str):
            author_info["name"] = name
        else:
            continue  # Skip if no valid name

        # Extract ORCID
        orcid = author.get("orcid")
        if orcid:
            author_info["orcid"] = orcid.strip()

        # Extract Wikidata QID
        qid = author.get("qid")
        if qid:
            author_info["qid"] = qid.strip()

        authors_data.append(author_info)

    logger.debug(f"Extracted {len(authors_data)} authors from {qmd_path.name}")
    return authors_data


# ============================================================================
# HTML PROCESSING
# ============================================================================


def find_author_elements(soup: BeautifulSoup) -> List:
    """Find author-related elements in HTML.

    Args:
        soup: BeautifulSoup object

    Returns:
        List of author elements
    """
    # Try different patterns Quarto might use
    author_elements = []

    # Pattern 1: author class
    author_elements.extend(soup.find_all(class_="author"))

    # Pattern 2: quarto-title-author-name class
    author_elements.extend(soup.find_all(class_="quarto-title-author-name"))

    # Pattern 3: author-meta class
    author_elements.extend(soup.find_all(class_="author-meta"))

    return author_elements


def _remove_existing_orcid_icons(author_elem) -> None:
    """Remove any existing ORCID icon elements to avoid duplicates or ugly bitmaps.
    Handles <img>, <svg>, and <i class="ai ai-orcid"> patterns.
    """
    # Remove <i> based icons (e.g., academicons)
    for tag in author_elem.find_all("i"):
        classes = tag.get("class", [])
        if (
            any(cls.startswith("ai") for cls in classes)
            or "orcid" in " ".join(classes).lower()
        ):
            tag.decompose()
    # Remove any direct SVGs labelled ORCID
    for svg in author_elem.find_all("svg"):
        # Heuristic: if title/aria-label mentions ORCID
        if svg.get("aria-label") and "orcid" in svg.get("aria-label").lower():
            svg.decompose()
    # Remove bitmap images that look like ORCID
    for img in author_elem.find_all("img"):
        src = (img.get("src") or "").lower()
        alt = (img.get("alt") or "").lower()
        if "orcid" in src or "orcid" in alt:
            img.decompose()


def inject_orcid_icon(soup: BeautifulSoup, orcid: str, author_elem) -> bool:
    """Inject vectorial ORCID icon next to author name using official SVG."""
    # Normalize: remove any previous icons
    _remove_existing_orcid_icons(author_elem)

    # Find existing ORCID link or create one
    existing_link = author_elem.find("a", href=lambda h: h and "orcid.org" in h)

    if existing_link:
        # Ensure anchor has only one clean SVG <img>
        # Remove any child images/icons inside the link
        for child_img in existing_link.find_all("img"):
            child_img.decompose()
        for child_i in existing_link.find_all("i"):
            child_i.decompose()
        # Append official SVG image
        existing_link.append(BeautifulSoup(ORCID_IMG_TAG, "html.parser"))
        # Normalize attributes
        existing_link["class"] = (existing_link.get("class") or []) + ["orcid-link"]
        existing_link["target"] = "_blank"
        existing_link["rel"] = "noopener noreferrer"
        existing_link["title"] = f"ORCID: {orcid}"
        # Fix href format if needed
        href = existing_link.get("href", "")
        if not href.endswith(orcid):
            existing_link["href"] = f"https://orcid.org/{orcid}"
        logger.debug(f"Normalized existing ORCID link for {orcid}")
        return True

    # If no link exists, try to detect plain ORCID ID text and wrap it
    text = author_elem.get_text(" ")
    # ORCID ID regex (0000-0000-0000-0000 with possible X last char)
    orcid_re = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", re.IGNORECASE)
    if orcid_re.search(text):
        # Create a new link right after author name
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

    # Otherwise, create a fresh link
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
    """Inject Scholia profile link next to author name using official SVG.

    Args:
        soup: BeautifulSoup object
        qid: Wikidata QID
        author_elem: Author HTML element

    Returns:
        True if link was injected
    """
    # Check if Scholia link already exists
    existing_link = author_elem.find(
        "a", href=lambda h: h and "scholia.toolforge.org" in h
    )
    if existing_link:
        logger.debug(f"Scholia link already exists for {qid}")
        return False

    # Create Scholia link with icon
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

    # Append to author element
    author_elem.append(scholia_link)
    logger.debug(f"Added Scholia link for {qid}")
    return True


def enrich_authors_in_html(
    soup: BeautifulSoup, authors_metadata: List[Dict[str, str]]
) -> int:
    """Enrich author elements with ORCID and Scholia links.

    Args:
        soup: BeautifulSoup object
        authors_metadata: List of author metadata dicts

    Returns:
        Number of authors enriched
    """
    if not authors_metadata:
        logger.debug("No author metadata to inject")
        return 0

    author_elements = find_author_elements(soup)
    if not author_elements:
        logger.debug("No author elements found in HTML")
        return 0

    enriched_count = 0

    # Match author elements to metadata by name
    for author_meta in authors_metadata:
        author_name = author_meta.get("name")
        if not author_name:
            continue

        # Find matching author element
        for author_elem in author_elements:
            elem_text = author_elem.get_text().strip()
            if author_name in elem_text or elem_text in author_name:
                # Inject ORCID icon if available
                if "orcid" in author_meta:
                    if inject_orcid_icon(soup, author_meta["orcid"], author_elem):
                        enriched_count += 1

                # Inject Scholia link if available
                if "qid" in author_meta:
                    if inject_scholia_link(soup, author_meta["qid"], author_elem):
                        enriched_count += 1

                break  # Move to next author in metadata

    return enriched_count


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def inject_author_links(qmd_path: Path, html_path: Path) -> None:
    """Inject ORCID and Scholia links into HTML based on QMD metadata.

    Args:
        qmd_path: Path to source QMD file
        html_path: Path to target HTML file
    """
    qmd_path = Path(qmd_path)
    html_path = Path(html_path)

    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    # Extract author metadata from QMD
    authors_metadata = extract_author_metadata(qmd_path)
    if not authors_metadata:
        logger.debug(f"No author metadata found in {qmd_path.name}")
        return

    # Read HTML
    try:
        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.error(f"Failed to read HTML {html_path}: {e}")
        return

    # Enrich authors
    enriched_count = enrich_authors_in_html(soup, authors_metadata)

    # Write back if changes were made
    if enriched_count > 0:
        try:
            html_path.write_text(str(soup), encoding="utf-8")
            logger.info(
                f"✓ Enriched {enriched_count} author elements in {html_path.name}"
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
