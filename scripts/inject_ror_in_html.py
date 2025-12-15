"""
ROR (Research Organization Registry) affiliation injector.

Extracts ROR IDs from _authors/*.yml files and QMD YAML frontmatter and
injects ROR links into corresponding HTML affiliation paragraphs.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from bs4 import BeautifulSoup
from ruamel.yaml import YAML

from yaml_utils import extract_yaml_frontmatter, load_yaml, load_metadata_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

ROR_ICON_URL = (
    "https://raw.githubusercontent.com/ror-community/ror-logos/"
    "refs/heads/main/ror-icon-rgb-transparent.svg"
)

ROR_IMG_TAG = (
    f'<img src="{ROR_ICON_URL}" alt="ROR logo" '
    f'style="height:14px; vertical-align:middle;" />'
)

SCHOLIA_SVG_URL = (
    "https://raw.githubusercontent.com/WDscholia/scholia/main/"
    "scholia/app/static/images/scholia_logo.svg"
)

SCHOLIA_IMG_TAG = (
    f'<img src="{SCHOLIA_SVG_URL}" alt="Scholia" '
    f'style="height:1em; vertical-align:middle; margin-left:0.25em;" />'
)


# ============================================================================
# YAML PROCESSING
# ============================================================================


def _parse_affiliation_defs_from_doc(doc: dict) -> Dict[str, Dict[str, str]]:
    """Parse affiliation definitions from a YAML document.

    Accepts both 'affiliations' (list) and 'affiliation' (singular) forms.
    Returns mapping: affiliation name -> {ror: url, qid: qid}
    """
    out: Dict[str, Dict[str, str]] = {}
    if not doc or not isinstance(doc, dict):
        return out

    # plural
    affs = doc.get("affiliations")
    if isinstance(affs, list):
        for aff in affs:
            if not isinstance(aff, dict):
                continue
            name = aff.get("name")
            if name:
                aff_data = {}
                ror = aff.get("ror")
                if ror:
                    aff_data["ror"] = str(ror).strip()
                qid = aff.get("qid")
                if qid:
                    aff_data["qid"] = str(qid).strip()
                if aff_data:
                    out[str(name).strip()] = aff_data

    # singular
    aff_single = doc.get("affiliation")
    if isinstance(aff_single, dict):
        name = aff_single.get("name")
        if name:
            aff_data = {}
            ror = aff_single.get("ror")
            if ror:
                aff_data["ror"] = str(ror).strip()
            qid = aff_single.get("qid")
            if qid:
                aff_data["qid"] = str(qid).strip()
            if aff_data:
                out[str(name).strip()] = aff_data

    return out


def load_affiliations(qmd_path: Path) -> Dict[str, Dict[str, str]]:
    """Load and merge affiliation definitions from metadata-files in QMD frontmatter.

    Precedence: metadata-files (in order) -> QMD frontmatter (QMD overrides).

    Args:
        qmd_path: Path to QMD file

    Returns:
        Dictionary mapping affiliation names to {ror: url, qid: qid}
    """
    merged: Dict[str, Dict[str, str]] = {}

    try:
        content = qmd_path.read_text(encoding="utf-8")
        yaml_str = extract_yaml_frontmatter(content)
        if yaml_str:
            yaml_loader = YAML(typ="safe")
            try:
                qmd_doc = yaml_loader.load(yaml_str) or {}

                # Load all metadata-files referenced in the frontmatter
                metadata_files = qmd_doc.get("metadata-files", [])
                if isinstance(metadata_files, list):
                    for metadata_path in metadata_files:
                        metadata_doc = load_metadata_file(
                            metadata_path, qmd_path.parent
                        )
                        if metadata_doc:
                            merged.update(
                                _parse_affiliation_defs_from_doc(metadata_doc)
                            )

                # Then apply any affiliation data from QMD frontmatter itself (overrides)
                merged.update(_parse_affiliation_defs_from_doc(qmd_doc))
            except Exception as e:
                logger.debug(f"Failed to parse QMD YAML frontmatter: {e}")
    except Exception:
        pass

    return merged


# ============================================================================
# HTML PROCESSING
# ============================================================================


def inject_ror_links(soup: BeautifulSoup, aff_dict: Dict[str, Dict[str, str]]) -> int:
    """Inject ROR and Scholia links into HTML affiliation paragraphs.

    Args:
        soup: BeautifulSoup object
        aff_dict: mapping affiliation name -> {ror: url, qid: qid}

    Returns:
        Number of affiliations enriched with ROR/Scholia links
    """
    enriched_count = 0

    # Find all paragraphs with 'affiliation' or 'affiliations' class
    affiliation_elements = []
    for p in soup.find_all("p"):
        classes = p.get("class", [])
        if any("affiliation" in str(cls).lower() for cls in classes):
            affiliation_elements.append(p)

    for aff_elem in affiliation_elements:
        # Skip if already has a ROR link
        existing_link = aff_elem.find(
            "a", class_="uri", href=lambda h: h and "ror.org" in h
        )
        if existing_link:
            continue

        # Get the text content
        aff_text = aff_elem.get_text().strip()

        # Try to find matching affiliation data
        aff_data = aff_dict.get(aff_text)
        if not aff_data:
            # Try case-insensitive match
            for name, data in aff_dict.items():
                if name.lower() == aff_text.lower():
                    aff_data = data
                    break

        if aff_data:
            # Add ROR link if available
            ror_url = aff_data.get("ror")
            if ror_url:
                ror_link = soup.new_tag("a", **{"class": "uri", "href": ror_url})
                ror_link.append(BeautifulSoup(ROR_IMG_TAG, "html.parser"))
                aff_elem.append(" ")
                aff_elem.append(ror_link)
                enriched_count += 1
                logger.debug(f"Added ROR link for affiliation: {aff_text}")

            # Add Scholia link if QID available
            qid = aff_data.get("qid")
            if qid:
                scholia_url = f"https://scholia.toolforge.org/organization/{qid}"
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
                aff_elem.append(" ")
                aff_elem.append(scholia_link)
                enriched_count += 1
                logger.debug(f"Added Scholia link for affiliation: {aff_text}")
        else:
            logger.debug(f"Affiliation data not found for: {aff_text}")

    return enriched_count


# ============================================================================
# MAIN
# ============================================================================


def inject_ror_in_html(qmd_path: Path, html_path: Path) -> None:
    """Inject ROR links into HTML file based on _authors/ files and QMD frontmatter.

    Only affiliation paragraphs are modified.

    Args:
        qmd_path: Path to QMD file
        html_path: Path to HTML file
    """
    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    # Load affiliation definitions
    aff_dict = load_affiliations(qmd_path)
    if not aff_dict:
        logger.debug(f"No affiliation definitions found for {qmd_path.name}")
        return

    # Read HTML content
    try:
        html_content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.error(f"Failed to read {html_path}: {e}")
        return

    # Inject ROR links into affiliation paragraphs
    enriched_count = inject_ror_links(soup, aff_dict)

    # Write back if changed
    if enriched_count > 0:
        try:
            html_path.write_text(str(soup), encoding="utf-8")
            logger.info(
                f"✓ Injected ROR links for {enriched_count} affiliation(s) in {html_path.name}"
            )
        except Exception as e:
            logger.error(f"Failed to write {html_path}: {e}")
    else:
        logger.debug(f"No ROR links added to {html_path.name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: inject_ror_in_html.py <qmd_path> <html_path>")
        sys.exit(1)

    inject_ror_in_html(Path(sys.argv[1]), Path(sys.argv[2]))
