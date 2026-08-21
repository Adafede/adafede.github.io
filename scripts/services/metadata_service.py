"""Metadata service for YAML header updates."""

import re
from pathlib import Path

import yaml

from scripts.config import DOI_URL_PREFIX
from scripts.infrastructure import FileSystem, get_logger

logger = get_logger(__name__)


class MetadataService:
    """Handles YAML metadata updates for posts."""

    YAML_FRONTMATTER_PATTERN: re.Pattern[str] = re.compile(
        r"^---\n(.*?)\n---\n(.*)$",
        re.DOTALL,
    )

    def __init__(self, filesystem: FileSystem):
        self.fs: FileSystem = filesystem

    def update_post_metadata(
        self,
        post_path: Path,
        generate_doi: bool = True,
    ) -> bool:
        """Update YAML frontmatter for a post.

        Ensures the ``date`` field matches the filename and generates a DOI
        when missing (if ``generate_doi`` is set).  Returns ``True`` if the
        file was written.
        """
        content = self.fs.read_text(post_path)

        match = self.YAML_FRONTMATTER_PATTERN.match(content)
        if match:
            front_matter, body = match.groups()
            data = yaml.safe_load(front_matter) or {}
        else:
            data = {}
            body = content

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

        if changed:
            self._write_frontmatter(post_path, data, body)
            logger.info(f"Updated metadata for {post_path.name}")

        return changed

    def _generate_doi(self) -> str:
        """Generate a stable DOI and strip the resolver URL prefix."""
        from commonmeta import encode_doi

        doi_url = encode_doi("10.59350")
        return doi_url.removeprefix(DOI_URL_PREFIX)

    def _write_frontmatter(
        self,
        path: Path,
        data: dict[str, object],
        body: str,
    ) -> None:
        """Write YAML frontmatter and body back to *path* with stable formatting."""

        # Custom YAML dumper for consistent formatting
        class CustomDumper(yaml.SafeDumper):
            def increase_indent(
                self,
                flow: bool = False,
                indentless: bool = False,
            ) -> None:
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
        """Update metadata for every post in *post_paths*.

        Returns the number of files that were modified.
        """
        logger.info(f"Updating metadata for {len(post_paths)} posts")

        modified = 0
        for path in post_paths:
            if self.update_post_metadata(path, generate_doi):
                modified += 1

        logger.info(f"Modified {modified} posts")
        return modified
