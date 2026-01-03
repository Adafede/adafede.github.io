"""CiTO (Citation Typing Ontology) service for parsing and injection."""

import re
from pathlib import Path
from typing import Optional

from bs4 import Tag

from domain.citation import Citation, CitationRegistry
from infrastructure.filesystem import FileSystem
from infrastructure.html_processor import HtmlProcessor
from infrastructure.logger import get_logger

logger = get_logger(__name__)


class CitoService:
    """Handles CiTO citation parsing and HTML injection."""

    # Pattern to match Pandoc citations: [@...]
    CITATION_PATTERN = re.compile(r"\[@([^\]]+)\]")

    # HTML element identifiers
    REFS_CONTAINER_ID = "refs"
    CSL_ENTRY_CLASS = "csl-entry"
    CITO_SPAN_CLASS = "cito"
    REF_ID_PREFIX = "ref-"

    def __init__(
        self,
        filesystem: FileSystem,
        html_processor: HtmlProcessor,
    ):
        """Initialize CiTO service.

        Args:
            filesystem: FileSystem instance
            html_processor: HtmlProcessor instance
        """
        self.fs = filesystem
        self.html = html_processor

    def parse_citations_from_qmd(self, qmd_path: Path) -> dict[str, set[str]]:
        """Parse CiTO citations from a QMD file.

        Args:
            qmd_path: Path to QMD file

        Returns:
            Dictionary mapping citation IDs to sets of CiTO properties
        """
        if not self.fs.exists(qmd_path):
            logger.warning(f"QMD file not found: {qmd_path}")
            return {}

        try:
            content = self.fs.read_text(qmd_path)
        except Exception as e:
            logger.error(f"Failed to read {qmd_path}: {e}")
            return {}

        # Find all citation matches
        matches = self.CITATION_PATTERN.findall(content)

        # Parse and merge citations
        from collections import defaultdict

        all_citos: dict[str, set[str]] = defaultdict(set)

        for match in matches:
            citation_dict = self._parse_citation_group(match)
            for cite_id, props in citation_dict.items():
                all_citos[cite_id].update(props)

        logger.debug(f"Parsed {len(all_citos)} citations from {qmd_path.name}")
        return dict(all_citos)

    def _parse_citation_group(self, citation_group: str) -> dict[str, set[str]]:
        """Parse a group of semicolon-separated citations.

        Args:
            citation_group: String with citations separated by semicolons

        Returns:
            Dictionary mapping citation IDs to sets of properties
        """
        from collections import defaultdict

        citos: dict[str, set[str]] = defaultdict(set)

        # Split by semicolon to get individual citations
        citations = [c.strip() for c in citation_group.split(";")]

        for citation in citations:
            if not citation:
                continue

            prop, cite_id = self._parse_single_citation(citation)
            citos[cite_id].add(prop)

        return dict(citos)

    def _parse_single_citation(self, citation: str) -> tuple[str, str]:
        """Parse a single citation into property and citation ID.

        Args:
            citation: Citation string (may include @ prefix)

        Returns:
            Tuple of (property, citation_id)
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
            return "citation", parts[0].strip()

    def merge_citations(
        self,
        cito_dicts: list[dict[str, set[str]]],
    ) -> dict[str, set[str]]:
        """Merge multiple citation dictionaries.

        Args:
            cito_dicts: List of citation dictionaries

        Returns:
            Merged dictionary with all unique citations
        """
        from collections import defaultdict

        merged: dict[str, set[str]] = defaultdict(set)

        for cito_dict in cito_dicts:
            for cite_id, properties in cito_dict.items():
                merged[cite_id].update(properties)

        return dict(merged)

    def inject_into_html(
        self,
        html_path: Path,
        citation_properties: dict[str, list[str]],
    ) -> bool:
        """Inject CiTO annotations into HTML bibliography entries.

        Args:
            html_path: Path to HTML file
            citation_properties: Dict mapping citation IDs to property lists

        Returns:
            True if file was modified, False otherwise
        """
        soup = self.html.load_from_path(html_path)
        if soup is None:
            return False

        # Find bibliography container
        refs_container = self.html.find_element_by_id(soup, self.REFS_CONTAINER_ID)
        if not refs_container:
            logger.debug(f"No refs container in {html_path}")
            return False

        # Process bibliography entries
        entries = self.html.find_elements_by_class(
            refs_container,
            self.CSL_ENTRY_CLASS,
            tag="div",
        )

        changed = False
        for entry in entries:
            if self._inject_citation_annotation(soup, entry, citation_properties):
                changed = True

        # Save if changed
        if changed:
            self.html.save_to_path(soup, html_path)
            logger.info(f"Injected CiTO annotations into {html_path.name}")

        return changed

    def _inject_citation_annotation(
        self,
        soup,
        entry: Tag,
        citation_properties: dict[str, list[str]],
    ) -> bool:
        """Inject CiTO annotation into a single bibliography entry.

        Args:
            soup: BeautifulSoup object
            entry: Bibliography entry element
            citation_properties: Citation properties dictionary

        Returns:
            True if entry was modified
        """
        # Get citation ID from entry
        cid = self.html.get_attribute(entry, "id", "")
        if not cid.startswith(self.REF_ID_PREFIX):
            return False

        cite_id = cid[len(self.REF_ID_PREFIX) :]
        cito_props = citation_properties.get(cite_id, [])

        if not cito_props:
            return False

        # Skip if already annotated
        if entry.find("span", class_=self.CITO_SPAN_CLASS):
            return False

        # Convert snake_case to camelCase
        camel_props = [self._snake_to_camel(prop) for prop in cito_props]
        annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_props)

        # Create and append annotation
        cito_span = self.html.create_element(
            soup,
            "span",
            text=" " + annotation_text,
            **{"class": self.CITO_SPAN_CLASS},
        )
        self.html.append_element(entry, cito_span)

        return True

    @staticmethod
    def _snake_to_camel(snake_str: str) -> str:
        """Convert snake_case to camelCase.

        Args:
            snake_str: Snake case string

        Returns:
            Camel case string
        """
        parts = snake_str.split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    def process_posts(
        self,
        post_paths: list[Path],
        site_dir: Path,
    ) -> dict[str, list[str]]:
        """Process all posts: parse citations and inject into HTML.

        Args:
            post_paths: List of post QMD file paths
            site_dir: Site output directory

        Returns:
            Merged citation properties dictionary
        """
        # Parse citations from all posts
        logger.info(f"Parsing citations from {len(post_paths)} posts")
        all_cito_dicts = [self.parse_citations_from_qmd(qmd) for qmd in post_paths]

        # Merge all citations
        merged = self.merge_citations(all_cito_dicts)
        citation_properties = {k: sorted(v) for k, v in merged.items()}

        logger.info(
            f"Merged {len(citation_properties)} unique citations "
            f"with {sum(len(v) for v in citation_properties.values())} properties"
        )

        # Inject into HTML files
        for qmd_path in post_paths:
            html_path = self.fs.get_html_path(qmd_path, str(site_dir))
            if self.fs.exists(html_path):
                self.inject_into_html(html_path, citation_properties)
            else:
                logger.warning(f"HTML not found for {qmd_path.name}")

        return citation_properties
