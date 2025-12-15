"""
CiTO annotation injector for RSS feeds.

Injects CiTO (Citation Typing Ontology) annotations into RSS feed item
descriptions, specifically into bibliography entries.
"""

import logging
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from lxml import etree

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
# RSS PROCESSING
# ============================================================================


def inject_cito_annotations_in_rss(
    rss_path: Path, citation_properties: Dict[str, List[str]]
) -> None:
    """Inject CiTO annotations into RSS feed bibliography entries.

    Args:
        rss_path: Path to RSS XML file
        citation_properties: Dictionary mapping citation IDs to lists of CiTO properties

    Example:
        >>> citation_props = {'smith2020': ['citesAsEvidence']}
        >>> inject_cito_annotations_in_rss(Path('posts.xml'), citation_props)
    """
    rss_path = Path(rss_path)

    if not rss_path.exists():
        logger.warning(f"RSS file not found: {rss_path}")
        return

    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(str(rss_path), parser)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Failed to parse RSS {rss_path}: {e}")
        return

    # Find items in channel
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []

    if not items:
        logger.debug(f"No items found in RSS feed {rss_path}")
        return

    modified = False

    for item in items:
        desc_elem = item.find("description")
        if desc_elem is None or not desc_elem.text:
            continue

        # Parse the inner HTML with BeautifulSoup
        try:
            soup = BeautifulSoup(desc_elem.text, "html.parser")
        except Exception as e:
            logger.warning(f"Failed to parse description HTML: {e}")
            continue

        # Find bibliography container
        refs_container = soup.find("div", id=REFS_CONTAINER_ID)
        if not refs_container:
            continue

        # Process bibliography entries
        bib_entries = refs_container.find_all("div", class_=CSL_ENTRY_CLASS)
        item_modified = False

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
            item_modified = True

        # Update description with CDATA section if modified
        if item_modified:
            desc_elem.clear()
            desc_elem.text = etree.CDATA(str(soup))
            modified = True

    # Write back if modified
    if modified:
        try:
            tree.write(
                str(rss_path), pretty_print=True, encoding="utf-8", xml_declaration=True
            )
            logger.info(f"Injected CiTO annotations into {rss_path.name}")
        except Exception as e:
            logger.error(f"Failed to write RSS {rss_path}: {e}")
    else:
        logger.debug(f"No CiTO annotations added to {rss_path.name}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: inject_cito_annotations_in_rss.py <rss_file>")
        sys.exit(1)

    # Example: inject some test annotations
    test_props = {
        "smith2020": ["citesAsEvidence", "supports"],
        "jones2021": ["usesDataFrom"],
    }
    inject_cito_annotations_in_rss(Path(sys.argv[1]), test_props)
