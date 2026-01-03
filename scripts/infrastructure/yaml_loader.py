"""YAML parsing and loading utilities."""

import re
from pathlib import Path
from typing import Optional

from ruamel.yaml import YAML

from .logger import get_logger

logger = get_logger(__name__)

# YAML frontmatter pattern for QMD files
YAML_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class YamlLoader:
    """Handles YAML file loading and QMD frontmatter extraction."""

    def __init__(self):
        """Initialize YAML loader with safe mode."""
        self._yaml = YAML(typ="safe")

    def extract_frontmatter(self, content: str) -> Optional[str]:
        """Extract YAML frontmatter from QMD content.

        Args:
            content: QMD file content

        Returns:
            YAML frontmatter string or None if not found
        """
        match = YAML_FRONTMATTER_PATTERN.match(content)
        return match.group(1) if match else None

    def load_from_path(self, path: Path) -> Optional[dict]:
        """Load YAML from file or QMD frontmatter.

        Args:
            path: Path to .yml or .qmd file

        Returns:
            Parsed YAML dictionary or None if not found/invalid
        """
        path = Path(path)

        if not path.exists():
            logger.debug(f"YAML file not found: {path}")
            return None

        try:
            content = path.read_text(encoding="utf-8")

            # Handle QMD files with frontmatter
            if path.suffix == ".qmd":
                yaml_str = self.extract_frontmatter(content)
                if yaml_str is None:
                    logger.warning(f"No YAML frontmatter in {path}")
                    return None
                return self._yaml.load(yaml_str)

            # Handle pure YAML files
            return self._yaml.load(content)

        except Exception as e:
            logger.warning(f"Failed to parse YAML from {path}: {e}")
            return None

    def load_from_string(self, yaml_str: str) -> Optional[dict]:
        """Parse YAML from string.

        Args:
            yaml_str: YAML content as string

        Returns:
            Parsed dictionary or None if invalid
        """
        try:
            return self._yaml.load(yaml_str)
        except Exception as e:
            logger.warning(f"Failed to parse YAML string: {e}")
            return None

    def dump_to_string(self, data: dict, **kwargs) -> str:
        """Dump dictionary to YAML string.

        Args:
            data: Dictionary to serialize
            **kwargs: Additional arguments for YAML dumper

        Returns:
            YAML string
        """
        from io import StringIO

        stream = StringIO()
        self._yaml.dump(data, stream, **kwargs)
        return stream.getvalue()

    def load_metadata_file(
        self,
        relative_path: str,
        base_dir: Path,
    ) -> Optional[dict]:
        """Load a metadata file referenced from frontmatter.

        Args:
            relative_path: Relative path from base directory
            base_dir: Base directory to resolve from

        Returns:
            Parsed YAML dictionary or None
        """
        full_path = (base_dir / relative_path).resolve()
        return self.load_from_path(full_path)

    def load_author_file(self, author_id: str, root_dir: Path) -> Optional[dict]:
        """Load author metadata from _authors/_<id>.yml file.

        Args:
            author_id: Author identifier (e.g., 'adriano')
            root_dir: Project root directory

        Returns:
            Author metadata dictionary or None
        """
        author_file = root_dir / "_authors" / f"_{author_id}.yml"
        return self.load_from_path(author_file)
