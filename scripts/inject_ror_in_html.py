"""
ROR (Research Organization Registry) affiliation injector.

Extracts ROR IDs from QMD YAML frontmatter and injects ROR links into
corresponding HTML affiliation paragraphs.
"""

import html as html_module
import logging
import re
from pathlib import Path
from typing import Dict, Optional

from ruamel.yaml import YAML

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

YAML_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
AFFILIATION_PATTERN = re.compile(r'(<p class="affiliation">\s*(.*?)\s*</p>)', re.DOTALL)


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


def parse_affiliations(yaml_data: dict) -> Dict[str, str]:
    """Parse affiliations from YAML data.

    Args:
        yaml_data: Parsed YAML data

    Returns:
        Dictionary mapping affiliation names to ROR URLs
    """
    affiliations = yaml_data.get("affiliations", [])
    if not isinstance(affiliations, list):
        logger.warning("Affiliations is not a list")
        return {}

    aff_dict = {}
    for aff in affiliations:
        if not isinstance(aff, dict):
            continue

        name = aff.get("name")
        ror = aff.get("ror")

        if name and ror:
            aff_dict[name.strip()] = ror.strip()

    return aff_dict


def load_affiliations_from_qmd(qmd_path: Path) -> Dict[str, str]:
    """Load affiliations from QMD file.

    Args:
        qmd_path: Path to QMD file

    Returns:
        Dictionary mapping affiliation names to ROR URLs
    """
    try:
        qmd_content = qmd_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {qmd_path}: {e}")
        return {}

    yaml_str = extract_yaml_frontmatter(qmd_content)
    if not yaml_str:
        logger.debug(f"No YAML frontmatter found in {qmd_path}")
        return {}

    yaml_loader = YAML(typ="safe")
    try:
        yaml_data = yaml_loader.load(yaml_str)
    except Exception as e:
        logger.error(f"Failed to parse YAML in {qmd_path}: {e}")
        return {}

    return parse_affiliations(yaml_data)


# ============================================================================
# HTML PROCESSING
# ============================================================================


def create_affiliation_replacement(
    original_tag: str,
    inner_html: str,
    ror_url: str,
) -> str:
    """Create replacement HTML for affiliation with ROR link.

    Args:
        original_tag: Original <p> tag
        inner_html: Inner HTML content
        ror_url: ROR URL

    Returns:
        New HTML with ROR link appended
    """
    return (
        f'<p class="affiliation">{inner_html} '
        f'<a class="uri" href="{ror_url}">'
        f'<img src="{ROR_ICON_URL}" '
        f'style="height:14px; vertical-align:middle;" '
        f'alt="ROR logo">'
        f"</a></p>"
    )


def inject_ror_links(html_content: str, aff_dict: Dict[str, str]) -> str:
    """Inject ROR links into HTML affiliation paragraphs.

    Args:
        html_content: HTML content
        aff_dict: Dictionary mapping affiliation names to ROR URLs

    Returns:
        Modified HTML content
    """

    def replace_affiliation(match: re.Match) -> str:
        """Replacement function for regex substitution."""
        full_tag = match.group(1)
        inner = match.group(2).strip()

        # Skip if already contains ROR link
        if 'class="uri"' in full_tag or 'href="https://ror.org/' in full_tag:
            return full_tag

        # Extract plain text (remove HTML tags)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        plain_unescaped = html_module.unescape(plain)

        # Check if affiliation is in dictionary
        if plain_unescaped in aff_dict:
            ror_url = aff_dict[plain_unescaped]
            return create_affiliation_replacement(full_tag, inner, ror_url)
        else:
            logger.debug(f"ROR ID not found for affiliation: {plain_unescaped}")
            return full_tag

    return AFFILIATION_PATTERN.sub(replace_affiliation, html_content)


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def inject_ror_in_html(qmd_path: Path, html_path: Path) -> None:
    """Inject ROR links into HTML file based on QMD metadata.

    Args:
        qmd_path: Path to source QMD file
        html_path: Path to target HTML file
    """
    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    # Load affiliations from QMD
    aff_dict = load_affiliations_from_qmd(qmd_path)
    if not aff_dict:
        logger.debug(f"No affiliations found in {qmd_path}")
        return

    # Read HTML content
    try:
        html_content = html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {html_path}: {e}")
        return

    # Inject ROR links
    new_html = inject_ror_links(html_content, aff_dict)

    # Write back if changed
    if new_html != html_content:
        try:
            html_path.write_text(new_html, encoding="utf-8")
            logger.info(f"Injected ROR links into {html_path.name}")
        except Exception as e:
            logger.error(f"Failed to write {html_path}: {e}")
    else:
        logger.debug(f"No changes made to {html_path.name}")


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) != 3:
        print("Usage: inject_ror_in_html.py <qmd_path> <html_path>")
        sys.exit(1)

    inject_ror_in_html(Path(sys.argv[1]), Path(sys.argv[2]))
