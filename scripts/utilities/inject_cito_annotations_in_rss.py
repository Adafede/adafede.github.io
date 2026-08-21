"""
CiTO annotation injector for RSS feeds.

Injects CiTO (Citation Typing Ontology) annotations into RSS feed item
descriptions, specifically into bibliography entries.
Uses the refactored infrastructure layer.
"""

import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from bs4 import BeautifulSoup

# Add project root to path so `scripts` is importable as a package
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from scripts.config import (
    CITO_SPAN_CLASS,
    CSL_ENTRY_CLASS,
    REF_ID_PREFIX,
    REFS_CONTAINER_ID,
)
from scripts.infrastructure import get_logger, snake_to_camel
from scripts.infrastructure.xml_parser import XmlParser

logger = get_logger(__name__)


def inject_cito_annotations_in_rss(
    rss_path: Path,
    citation_properties: Mapping[str, Iterable[str]],
) -> None:
    """Inject [cito:...] annotations into bibliography entries in an RSS feed's
    item descriptions.

    Args:
        rss_path: Path to RSS XML file.
        citation_properties: Mapping of citation IDs to CiTO property lists,
            e.g. ``{"smith2020": ["cites_as_evidence"]}``.
    """
    rss_path = Path(rss_path)

    if not rss_path.exists():
        logger.warning(f"RSS file not found: {rss_path}")
        return

    try:
        parser = XmlParser.new_parser(remove_blank_text=True)
        root = XmlParser.parse(str(rss_path), parser=parser)
    except (OSError, XmlParser.ParseError) as e:
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
            soup = BeautifulSoup(str(desc_elem.text), "html.parser")
        except (ValueError, TypeError):
            logger.warning("Failed to parse description HTML")
            continue

        # Find bibliography container
        refs_container = soup.find("div", id=REFS_CONTAINER_ID)
        if not refs_container:
            continue

        # Process bibliography entries
        bib_entries = refs_container.find_all("div", class_=CSL_ENTRY_CLASS)
        item_modified = False

        for entry in bib_entries:
            cid = str(entry.get("id") or "")
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
            camel_case_props = [snake_to_camel(prop) for prop in cito_props]
            annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_case_props)

            # Create and append CiTO annotation span
            cito_span = soup.new_tag("span", attrs={"class": CITO_SPAN_CLASS})
            cito_span.string = " " + annotation_text
            _ = entry.append(cito_span)
            item_modified = True

        # Update description with CDATA section if modified
        if item_modified:
            desc_elem.clear()
            cdata_node = XmlParser.cdata(str(soup))
            desc_elem.text = cast("str | None", cdata_node)
            modified = True

    # Write back if modified
    if modified:
        try:
            XmlParser.write(root, str(rss_path))
            logger.info(f"Injected CiTO annotations into {rss_path.name}")
        except OSError as e:
            logger.error(f"Failed to write RSS {rss_path}: {e}")
    else:
        logger.debug(f"No CiTO annotations added to {rss_path.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: inject_cito_annotations_in_rss.py <rss_file>")
        sys.exit(1)

    # Example: inject some test annotations
    test_props = {
        "smith2020": ["citesAsEvidence", "supports"],
        "jones2021": ["usesDataFrom"],
    }
    inject_cito_annotations_in_rss(Path(sys.argv[1]), test_props)
