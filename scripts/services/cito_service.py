"""CiTO (Citation Typing Ontology) service for parsing and injection."""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from scripts.config import (
    CITO_SPAN_CLASS,
    CSL_ENTRY_CLASS,
    REF_ID_PREFIX,
    REFS_CONTAINER_ID,
)
from scripts.infrastructure import FileSystem, HtmlProcessor, get_logger, snake_to_camel

logger = get_logger(__name__)


class CitoService:
    """Handles CiTO citation parsing and HTML injection."""

    # Pattern to match Pandoc citations: [@...]
    CITATION_PATTERN = re.compile(r"\[@([^\]]+)\]")

    def __init__(
        self,
        filesystem: FileSystem,
        html_processor: HtmlProcessor,
    ):
        self.fs = filesystem
        self.html = html_processor

    def parse_citations_from_qmd(self, qmd_path: Path) -> dict[str, set[str]]:
        """Parse CiTO citations from a QMD file into {cite_id: {properties}}."""
        if not self.fs.exists(qmd_path):
            logger.warning(f"QMD file not found: {qmd_path}")
            return {}

        try:
            content = self.fs.read_text(qmd_path)
        except OSError as e:
            logger.error(f"Failed to read {qmd_path}: {e}")
            return {}

        matches = self.CITATION_PATTERN.findall(content)
        all_citos: dict[str, set[str]] = defaultdict(set)

        for match in matches:
            citation_dict = self._parse_citation_group(match)
            for cite_id, props in citation_dict.items():
                all_citos[cite_id].update(props)

        logger.debug(f"Parsed {len(all_citos)} citations from {qmd_path.name}")
        return dict(all_citos)

    def _parse_citation_group(self, citation_group: str) -> dict[str, set[str]]:
        """Parse semicolon-separated citations into {cite_id: {properties}}."""
        citos: dict[str, set[str]] = defaultdict(set)

        for citation in (c.strip() for c in citation_group.split(";") if c.strip()):
            prop, cite_id = self._parse_single_citation(citation)
            citos[cite_id].add(prop)

        return dict(citos)

    def _parse_single_citation(self, citation: str) -> tuple[str, str]:
        """Parse one citation into a (property, citation_id) tuple."""
        citation = citation.strip()
        if citation.startswith("@"):
            citation = citation[1:].strip()

        parts = citation.split(":", 1)
        if len(parts) == 2:
            prop, cite_id = parts
            return prop.strip(), cite_id.strip()

        # No property specified, use default
        return "citation", parts[0].strip()

    def merge_citations(
        self,
        cito_dicts: list[dict[str, set[str]]],
    ) -> dict[str, set[str]]:
        """Merge multiple citation dictionaries into one."""
        merged: dict[str, set[str]] = defaultdict(set)

        for cito_dict in cito_dicts:
            for cite_id, properties in cito_dict.items():
                merged[cite_id].update(properties)

        return dict(merged)

    def inject_into_html(
        self,
        html_path: Path,
        citation_properties: Mapping[str, Iterable[str]],
    ) -> bool:
        """Inject CiTO annotations into bibliography entries in an HTML file.

        Returns ``True`` if the file was modified.
        """
        soup = self.html.load_from_path(html_path)
        if soup is None:
            return False

        refs_container = self.html.find_element_by_id(soup, REFS_CONTAINER_ID)
        if not refs_container:
            logger.debug(f"No refs container in {html_path}")
            return False

        entries = self.html.find_elements_by_class(
            refs_container,
            CSL_ENTRY_CLASS,
            tag="div",
        )

        changed = False
        for entry in entries:
            if self._inject_citation_annotation(soup, entry, citation_properties):
                changed = True

        if changed:
            self.html.save_to_path(soup, html_path)
            logger.info(f"Injected CiTO annotations into {html_path.name}")

        return changed

    def _inject_citation_annotation(
        self,
        soup: BeautifulSoup,
        entry: Tag,
        citation_properties: Mapping[str, Iterable[str]],
    ) -> bool:
        """Inject a [cito:...] annotation span into one bibliography entry."""
        cid = self.html.get_attribute(entry, "id", "") or ""
        if not cid.startswith(REF_ID_PREFIX):
            return False

        cite_id = cid[len(REF_ID_PREFIX) :]
        cito_props = citation_properties.get(cite_id, [])

        if not cito_props:
            return False

        # Skip if already annotated
        if entry.find("span", class_=CITO_SPAN_CLASS):
            return False

        camel_props = [snake_to_camel(prop) for prop in cito_props]
        annotation_text = " ".join(f"[cito:{prop}]" for prop in camel_props)

        cito_span = self.html.create_element(
            soup,
            "span",
            text=" " + annotation_text,
            **{"class": CITO_SPAN_CLASS},
        )
        self.html.append_element(entry, cito_span)

        return True

    def process_posts(
        self,
        post_paths: list[Path],
        site_dir: Path,
    ) -> dict[str, list[str]]:
        """Parse citations from all posts and inject CiTO annotations into HTML."""
        logger.info(f"Parsing citations from {len(post_paths)} posts")
        all_cito_dicts = [self.parse_citations_from_qmd(qmd) for qmd in post_paths]

        merged = self.merge_citations(all_cito_dicts)
        citation_properties = {k: sorted(v) for k, v in merged.items()}

        logger.info(
            f"Merged {len(citation_properties)} unique citations "
            f"with {sum(len(v) for v in citation_properties.values())} properties",
        )

        for qmd_path in post_paths:
            html_path = self.fs.get_html_path(qmd_path, str(site_dir))
            if self.fs.exists(html_path):
                self.inject_into_html(html_path, citation_properties)
            else:
                logger.warning(f"HTML not found for {qmd_path.name}")

        return citation_properties
