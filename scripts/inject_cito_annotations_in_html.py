"""
CiTO annotation injector for HTML files.

Injects CiTO (Citation Typing Ontology) annotations into HTML bibliography
entries based on parsed citation properties.
"""

import logging
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup

from snake_to_camel_case import snake_to_camel_case

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

REFS_CONTAINER_ID = "refs"
CSL_ENTRY_CLASS = "csl-entry"
CITO_SPAN_CLASS = "cito"
REF_ID_PREFIX = "ref-"


# ============================================================================
# CITO INJECTION
# ============================================================================


def inject_cito_annotations_in_html(
    html_path: Path,
    citation_properties: Dict[str, List[str]],
) -> None:
    """Inject CiTO annotations into HTML bibliography entries.

    Args:
        html_path: Path to HTML file
        citation_properties: Dictionary mapping citation IDs to lists of CiTO properties

    Example:
        >>> citation_props = {'smith2020': ['citesAsEvidence', 'supports']}
        >>> inject_cito_annotations_in_html(Path('post.html'), citation_props)
    """
    html_path = Path(html_path)

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    try:
        with open(html_path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
    except Exception as e:
        logger.error(f"Failed to read {html_path}: {e}")
        return

    # Find bibliography container
    refs_container = soup.find("div", id=REFS_CONTAINER_ID)
    if not refs_container:
        logger.debug(f"No refs container found in {html_path}")
        return

    # Process bibliography entries
    bib_entries = refs_container.find_all("div", class_=CSL_ENTRY_CLASS)
    changed = False

    for entry in bib_entries:
        cid = entry.get("id", "")
        if not cid.startswith(REF_ID_PREFIX):
            continue

        # Extract citation ID
        cite_id = cid[len(REF_ID_PREFIX) :]
        cito_props = citation_properties.get(cite_id, [])
        if not cito_props:
            continue

        # Skip if already annotated
        if entry.find("span", class_=CITO_SPAN_CLASS):
            continue

        # Transform snake_case properties to camelCase
        camel_case_props = [snake_to_camel_case(prop) for prop in cito_props]
        annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_case_props)

        # Create and append CiTO annotation span
        cito_span = soup.new_tag("span", **{"class": CITO_SPAN_CLASS})
        cito_span.string = " " + annotation_text
        entry.append(cito_span)
        changed = True

    # Write back if changed
    if changed:
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(str(soup))
            logger.info(f"Injected CiTO annotations into {html_path.name}")
        except Exception as e:
            logger.error(f"Failed to write {html_path}: {e}")
    else:
        logger.debug(f"No CiTO annotations added to {html_path.name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: inject_cito_annotations_in_html.py <html_file>")
        sys.exit(1)

    # Example: inject some test annotations
    test_props = {
        "smith2020": ["citesAsEvidence", "supports"],
        "jones2021": ["usesDataFrom"],
    }
    inject_cito_annotations_in_html(Path(sys.argv[1]), test_props)
