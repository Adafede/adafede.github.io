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
# Match <p> with class attribute containing 'affiliation' or 'affiliations' (possibly among others)
AFFILIATION_PATTERN = re.compile(
    r'(<p class="([^\"]*?(?:\baffiliation\b|\baffiliations\b)[^\"]*)">\s*(.*?)\s*</p>)',
    re.DOTALL,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _load_yaml(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    yaml_loader = YAML(typ="safe")
    try:
        return yaml_loader.load(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse YAML at {path}: {e}")
        return None


def _parse_affiliation_defs_from_doc(doc: dict) -> Dict[str, str]:
    """Parse affiliation definitions from a YAML document.

    Accepts both 'affiliations' (list) and 'affiliation' (singular) forms.
    Returns mapping: affiliation name -> ror url
    """
    out: Dict[str, str] = {}
    if not doc or not isinstance(doc, dict):
        return out

    # plural
    affs = doc.get("affiliations")
    if isinstance(affs, list):
        for aff in affs:
            if not isinstance(aff, dict):
                continue
            name = aff.get("name")
            ror = aff.get("ror")
            if name and ror:
                out[str(name).strip()] = str(ror).strip()

    # singular
    aff_single = doc.get("affiliation")
    if isinstance(aff_single, dict):
        name = aff_single.get("name")
        ror = aff_single.get("ror")
        if name and ror:
            out[str(name).strip()] = str(ror).strip()

    return out


def load_affiliations(qmd_path: Path) -> Dict[str, str]:
    """Load and merge affiliation definitions from repo _metadata.yaml, folder _metadata.yaml, and QMD frontmatter.

    Precedence: repo root -> folder -> QMD frontmatter (QMD overrides folder overrides repo).
    """
    merged: Dict[str, str] = {}

    # repo root _metadata.yaml
    root_meta = REPO_ROOT / "_metadata.yaml"
    root_doc = _load_yaml(root_meta)
    if root_doc:
        merged.update(_parse_affiliation_defs_from_doc(root_doc))

    # folder-level _metadata.yaml
    folder_meta = qmd_path.parent / "_metadata.yaml"
    folder_doc = _load_yaml(folder_meta)
    if folder_doc:
        merged.update(_parse_affiliation_defs_from_doc(folder_doc))

    # QMD frontmatter (overrides)
    try:
        content = qmd_path.read_text(encoding="utf-8")
    except Exception:
        # no QMD available; return merged metadata only
        return merged

    yaml_str = extract_yaml_frontmatter(content)
    if yaml_str:
        yaml_loader = YAML(typ="safe")
        try:
            qdoc = yaml_loader.load(yaml_str) or {}
            merged.update(_parse_affiliation_defs_from_doc(qdoc))
        except Exception as e:
            logger.debug(f"Failed to parse QMD YAML frontmatter: {e}")

    return merged


# ============================================================================
# HTML PROCESSING
# ============================================================================


def create_affiliation_replacement(p_class: str, inner_html: str, ror_url: str) -> str:
    return (
        f'<p class="{p_class}">{inner_html} '
        f'<a class="uri" href="{ror_url}">'
        f'<img src="{ROR_ICON_URL}" style="height:14px; vertical-align:middle;" alt="ROR logo">'
        f"</a></p>"
    )


def inject_ror_links(html_content: str, aff_dict: Dict[str, str]) -> str:
    """Inject ROR links into HTML affiliation paragraphs.

    Args:
        html_content: HTML content
        aff_dict: mapping affiliation name -> ror url
    Returns:
        Modified HTML content
    """

    def replace_affiliation(match: re.Match) -> str:
        full_tag = match.group(1)
        p_class = match.group(2)
        inner = match.group(3).strip()

        # Skip if already contains ROR link
        if 'class="uri"' in full_tag or 'href="https://ror.org/' in full_tag:
            return full_tag

        # Extract plain text (remove HTML tags)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        plain_unescaped = html_module.unescape(plain)

        # Try exact match then case-insensitive
        ror_url = aff_dict.get(plain_unescaped)
        if not ror_url:
            for name, url in aff_dict.items():
                if name.lower() == plain_unescaped.lower():
                    ror_url = url
                    break

        if ror_url:
            return create_affiliation_replacement(p_class, inner, ror_url)
        else:
            logger.debug(f"ROR ID not found for affiliation: {plain_unescaped}")
            return full_tag

    return AFFILIATION_PATTERN.sub(replace_affiliation, html_content)


# ============================================================================
# MAIN
# ============================================================================


def inject_ror_in_html(qmd_path: Path, html_path: Path) -> None:
    """Inject ROR links into HTML file based on _metadata.yaml and QMD frontmatter.

    Only affiliation paragraphs are modified (not author paragraphs).
    """
    if not qmd_path.exists():
        logger.warning(f"QMD file not found: {qmd_path}")
        return

    if not html_path.exists():
        logger.warning(f"HTML file not found: {html_path}")
        return

    # Load affiliation definitions from metadata + QMD
    aff_dict = load_affiliations(qmd_path)
    if not aff_dict:
        logger.debug(f"No affiliation definitions found for {qmd_path.name}")
        return

    # Read HTML content
    try:
        html_content = html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {html_path}: {e}")
        return

    # Inject into affiliation paragraphs only
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
    import sys

    if len(sys.argv) != 3:
        print("Usage: inject_ror_in_html.py <qmd_path> <html_path>")
        sys.exit(1)

    inject_ror_in_html(Path(sys.argv[1]), Path(sys.argv[2]))
