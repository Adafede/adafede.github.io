"""Metadata service for YAML header updates."""

import re
from pathlib import Path

import yaml

from infrastructure.filesystem import FileSystem
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class MetadataService:
    """Handles YAML metadata updates for posts."""

    YAML_FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

    def __init__(self, filesystem: FileSystem):
        """Initialize metadata service.

        Args:
            filesystem: FileSystem instance
        """
        self.fs = filesystem

    def update_post_metadata(
        self,
        post_path: Path,
        generate_doi: bool = True,
    ) -> bool:
        """Update YAML frontmatter for a post.

        Updates:
        - date: extracted from filename if not present
        - doi: generated if not present (when generate_doi=True)

        Args:
            post_path: Path to post QMD file
            generate_doi: Whether to generate DOI if missing

        Returns:
            True if file was modified, False otherwise
        """
        content = self.fs.read_text(post_path)

        # Parse frontmatter
        match = self.YAML_FRONTMATTER_PATTERN.match(content)
        if match:
            front_matter, body = match.groups()
            data = yaml.safe_load(front_matter) or {}
        else:
            data = {}
            body = content

        # Only proceed if no DOI exists (or if we don't care about DOI)
        if "doi" in data and not generate_doi:
            return False

        changed = False

        # Update date from filename if needed
        date_str = self.fs.extract_date_from_filename(post_path)
        if data.get("date") != date_str:
            data["date"] = date_str
            changed = True

        # Generate DOI if missing
        if generate_doi and "doi" not in data:
            data["doi"] = self._generate_doi()
            changed = True

        # Write back if changed
        if changed:
            self._write_frontmatter(post_path, data, body)
            logger.info(f"Updated metadata for {post_path.name}")

        return changed

    def _generate_doi(self) -> str:
        """Generate a new DOI.

        Returns:
            DOI string (without https://doi.org/ prefix)
        """
        from commonmeta import encode_doi

        doi_url = encode_doi("10.59350")
        return doi_url.removeprefix("https://doi.org/")

    def _write_frontmatter(
        self,
        path: Path,
        data: dict,
        body: str,
    ) -> None:
        """Write YAML frontmatter and body to file.

        Args:
            path: File path
            data: Frontmatter data dictionary
            body: Document body
        """

        # Custom YAML dumper for consistent formatting
        class CustomDumper(yaml.SafeDumper):
            def increase_indent(self, flow=False, indentless=False):
                return super().increase_indent(flow, False)

        new_front = yaml.dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_style=None,
            indent=2,
            default_flow_style=False,
            width=float("inf"),
            Dumper=CustomDumper,
        )

        # Clean up quotes (remove from dates, convert single to double)
        lines = new_front.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("date:"):
                # Remove any quotes from dates
                lines[i] = line.replace('"', "").replace("'", "")
            elif "'" in line:
                lines[i] = line.replace("'", '"')

        new_front = "\n".join(lines)
        new_content = f"---\n{new_front}---\n\n{body.lstrip()}"

        self.fs.write_text(path, new_content)

    def update_all_posts(
        self,
        post_paths: list[Path],
        generate_doi: bool = True,
    ) -> int:
        """Update metadata for multiple posts.

        Args:
            post_paths: List of post paths
            generate_doi: Whether to generate DOIs

        Returns:
            Number of posts modified
        """
        logger.info(f"Updating metadata for {len(post_paths)} posts")

        modified = 0
        for path in post_paths:
            if self.update_post_metadata(path, generate_doi):
                modified += 1

        logger.info(f"Modified {modified} posts")
        return modified
