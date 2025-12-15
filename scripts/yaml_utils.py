"""
Shared YAML utilities for metadata extraction.

Common functions for loading and parsing YAML frontmatter and metadata files.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

# YAML frontmatter pattern
YAML_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# Repository root path
REPO_ROOT = Path(__file__).resolve().parents[1]


def extract_yaml_frontmatter(qmd_content: str) -> Optional[str]:
    """Extract YAML frontmatter from QMD content.

    Args:
        qmd_content: Content of QMD file

    Returns:
        YAML frontmatter string or None if not found
    """
    match = YAML_FRONTMATTER_PATTERN.match(qmd_content)
    return match.group(1) if match else None


def load_yaml(path: Path) -> Optional[dict]:
    """Load and parse a YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML dict or None if file doesn't exist or can't be parsed
    """
    if not path.exists():
        return None
    yaml_loader = YAML(typ="safe")
    try:
        return yaml_loader.load(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse YAML at {path}: {e}")
        return None


# Helper to load shared author data


def load_authors_from_id(author_id: str) -> Optional[dict]:
    """Load author data from _authors/_<id>.yml file.

    Args:
        author_id: Author ID (e.g., 'adriano' for _authors/_adriano.yml)

    Returns:
        Parsed YAML dict with authors and affiliations, or None if not found
    """
    author_file = REPO_ROOT / "_authors" / f"_{author_id}.yml"
    return load_yaml(author_file)


def load_metadata_file(relative_path: str, qmd_dir: Path) -> Optional[dict]:
    """Load a metadata file referenced from QMD frontmatter.

    Args:
        relative_path: Relative path from QMD file (e.g., '../_authors/AdrianoRutz_IMSB.yml')
        qmd_dir: Directory containing the QMD file

    Returns:
        Parsed YAML dict or None if not found
    """
    full_path = (qmd_dir / relative_path).resolve()
    return load_yaml(full_path)
