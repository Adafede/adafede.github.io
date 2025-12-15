"""
CiTO citation parser for Quarto QMD files.

Extracts CiTO (Citation Typing Ontology) properties from Pandoc-style
citations in QMD files.

Citation format: [@cito_property:cite_id]
Example: [@citesAsEvidence:smith2020; @supports:jones2021]
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Set, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

# Pattern to match Pandoc citations: [@...]
CITATION_PATTERN = re.compile(r"\[@([^\]]+)\]")

# Default CiTO property when none is specified
DEFAULT_CITO_PROPERTY = "citation"


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================


def parse_single_citation(citation: str) -> tuple[str, str]:
    """Parse a single citation into CiTO property and citation ID.

    Args:
        citation: Citation string (may include @ prefix)

    Returns:
        Tuple of (property, citation_id)

    Examples:
        >>> parse_single_citation("@citesAsEvidence:smith2020")
        ('citesAsEvidence', 'smith2020')
        >>> parse_single_citation("smith2020")
        ('citation', 'smith2020')
    """
    # Remove leading @ if present
    citation = citation.strip()
    if citation.startswith("@"):
        citation = citation[1:].strip()

    # Split by colon to get property and ID
    parts = citation.split(":", 1)

    if len(parts) == 2:
        prop, cite_id = parts
        return prop.strip(), cite_id.strip()
    else:
        # No property specified, use default
        return DEFAULT_CITO_PROPERTY, parts[0].strip()


def parse_citation_group(citation_group: str) -> Dict[str, Set[str]]:
    """Parse a group of semicolon-separated citations.

    Args:
        citation_group: String containing one or more citations separated by semicolons

    Returns:
        Dictionary mapping citation IDs to sets of CiTO properties

    Examples:
        >>> parse_citation_group("citesAsEvidence:smith2020; supports:jones2021")
        {'smith2020': {'citesAsEvidence'}, 'jones2021': {'supports'}}
    """
    citos: Dict[str, Set[str]] = defaultdict(set)

    # Split by semicolon to get individual citations
    citations = [c.strip() for c in citation_group.split(";")]

    for citation in citations:
        if not citation:
            continue

        prop, cite_id = parse_single_citation(citation)
        citos[cite_id].add(prop)

    return dict(citos)


def parse_citos_from_qmd(qmd_path: Union[str, Path]) -> Dict[str, Set[str]]:
    """Parse CiTO citations from a QMD file.

    Args:
        qmd_path: Path to QMD file (string or Path object)

    Returns:
        Dictionary mapping citation IDs to sets of CiTO properties

    Example:
        >>> citos = parse_citos_from_qmd("posts/my-post.qmd")
        >>> citos
        {'smith2020': {'citesAsEvidence', 'supports'}, 'jones2021': {'citation'}}
    """
    qmd_path = Path(qmd_path)

    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return {}

    try:
        content = qmd_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {qmd_path}: {e}")
        return {}

    # Find all citation matches
    matches = CITATION_PATTERN.findall(content)

    # Merge all citations
    all_citos: Dict[str, Set[str]] = defaultdict(set)

    for match in matches:
        citation_dict = parse_citation_group(match)
        for cite_id, props in citation_dict.items():
            all_citos[cite_id].update(props)

    logger.debug(f"Parsed {len(all_citos)} citations from {qmd_path.name}")
    return dict(all_citos)


# ============================================================================
# MAIN ENTRY POINT (for testing)
# ============================================================================


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: parse_citos_from_qmd.py <qmd_file>")
        sys.exit(1)

    result = parse_citos_from_qmd(sys.argv[1])

    print(f"\nFound {len(result)} citations:")
    for cite_id, props in sorted(result.items()):
        print(f"  {cite_id}: {', '.join(sorted(props))}")
