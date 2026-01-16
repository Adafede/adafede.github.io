"""Author service for ORCID and Scholia link injection."""

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from infrastructure.filesystem import FileSystem
from infrastructure.html_processor import HtmlProcessor
from infrastructure.logger import get_logger
from infrastructure.yaml_loader import YamlLoader

logger = get_logger(__name__)


class AuthorService:
    """Handles author metadata enrichment (ORCID icons, Scholia links)."""

    # Official SVG assets from Scholia repository
    ORCID_SVG_URL = (
        "https://raw.githubusercontent.com/WDscholia/scholia/main/"
        "scholia/app/static/images/orcid.svg"
    )

    SCHOLIA_SVG_URL = (
        "https://raw.githubusercontent.com/WDscholia/scholia/main/"
        "scholia/app/static/images/scholia_logo.svg"
    )

    def __init__(
        self,
        filesystem: FileSystem,
        html_processor: HtmlProcessor,
        yaml_loader: YamlLoader,
    ):
        """Initialize author service.

        Args:
            filesystem: FileSystem instance
            html_processor: HtmlProcessor instance
            yaml_loader: YamlLoader instance
        """
        self.fs = filesystem
        self.html = html_processor
        self.yaml = yaml_loader

    def extract_author_metadata(self, qmd_path: Path) -> list[dict[str, str]]:
        """Extract author metadata from QMD file and metadata files.

        Args:
            qmd_path: Path to QMD file

        Returns:
            List of author metadata dictionaries
        """
        authors_by_key: dict[str, dict[str, str]] = {}

        # Load QMD frontmatter
        metadata = self.yaml.load_from_path(qmd_path)
        if not metadata:
            return []

        # Load from metadata-files
        metadata_files = metadata.get("metadata-files", [])
        if isinstance(metadata_files, list):
            for metadata_path in metadata_files:
                metadata_doc = self.yaml.load_metadata_file(
                    metadata_path,
                    qmd_path.parent,
                )
                if metadata_doc:
                    authors = self._parse_authors(metadata_doc)
                    self._merge_authors(authors_by_key, authors)

        # Apply authors from QMD frontmatter (overrides)
        qmd_authors = self._parse_authors(metadata)
        self._merge_authors(authors_by_key, qmd_authors)

        authors_data = list(authors_by_key.values())
        logger.debug(f"Extracted {len(authors_data)} authors from {qmd_path.name}")
        return authors_data

    def _parse_authors(self, doc: dict) -> list[dict[str, str]]:
        """Parse author metadata from YAML document.

        Args:
            doc: YAML document dictionary

        Returns:
            List of author metadata dictionaries
        """
        if not doc or not isinstance(doc, dict):
            return []

        authors_data = []

        # Handle both 'author' (singular) and 'authors' (plural)
        author_field = doc.get("author")
        if author_field is None:
            author_field = doc.get("authors", [])

        # Normalize to list
        if isinstance(author_field, dict):
            author_field = [author_field]
        elif not isinstance(author_field, list):
            return []

        for author in author_field:
            if not isinstance(author, dict):
                continue

            # Copy all author fields
            author_info = author.copy()

            # Normalize name field
            name = author.get("name")
            computed_name: Optional[str] = None

            if isinstance(name, dict):
                # Prefer explicit literal form
                literal = name.get("literal")
                if isinstance(literal, str) and literal.strip():
                    computed_name = literal.strip()
                else:
                    given = name.get("given", "")
                    family = name.get("family", "")
                    computed_name = f"{given} {family}".strip()
            elif isinstance(name, str):
                computed_name = name.strip()

            if not computed_name:
                continue

            author_info["_computed_name"] = computed_name
            authors_data.append(author_info)

        return authors_data

    def _merge_authors(
        self,
        authors_by_key: dict[str, dict[str, str]],
        new_authors: list[dict[str, str]],
    ) -> None:
        """Merge authors into dictionary by id or name.

        Args:
            authors_by_key: Dictionary to merge into
            new_authors: New authors to merge
        """
        for author in new_authors:
            key = author.get("id") or author.get("_computed_name")
            if not key:
                continue

            if key in authors_by_key:
                authors_by_key[key].update(author)
            else:
                authors_by_key[key] = author.copy()

    def inject_into_html(
        self,
        qmd_path: Path,
        html_path: Path,
    ) -> int:
        """Inject ORCID icons and Scholia links into HTML.

        Args:
            qmd_path: Path to QMD source file
            html_path: Path to HTML output file

        Returns:
            Number of enrichments made
        """
        # Extract author metadata
        authors = self.extract_author_metadata(qmd_path)
        if not authors:
            logger.debug(f"No authors found for {qmd_path.name}")
            return 0

        # Load HTML
        soup = self.html.load_from_path(html_path)
        if soup is None:
            return 0

        # Inject links
        enriched_count = self._inject_author_links(soup, authors)

        # Save if changed
        if enriched_count > 0:
            self.html.save_to_path(soup, html_path)
            logger.info(
                f"✓ Injected author links for {enriched_count} author(s) "
                f"in {html_path.name}",
            )

        return enriched_count

    def _inject_author_links(
        self,
        soup: BeautifulSoup,
        authors: list[dict[str, str]],
    ) -> int:
        """Inject ORCID and Scholia links for authors.

        Args:
            soup: BeautifulSoup object
            authors: List of author metadata dictionaries

        Returns:
            Number of enrichments made
        """
        enriched_count = 0

        # Find author elements
        author_elements = self._find_author_elements(soup)

        for author_elem in author_elements:
            author_text = author_elem.get_text(" ").strip()

            # Find matching author data
            author_data = self._find_author_data(author_text, authors)

            if author_data:
                # Add ORCID icon
                orcid = author_data.get("orcid")
                if orcid:
                    if self._inject_orcid_icon(soup, author_elem, orcid):
                        enriched_count += 1

                # Add Scholia link
                qid = author_data.get("qid")
                if qid:
                    if self._inject_scholia_link(soup, author_elem, qid):
                        enriched_count += 1

        return enriched_count

    def _find_author_elements(self, soup: BeautifulSoup) -> list:
        """Find author-related elements in HTML.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of author elements
        """
        author_elements = []
        author_elements.extend(soup.find_all(class_="author"))
        author_elements.extend(soup.find_all(class_="quarto-title-author-name"))
        author_elements.extend(soup.find_all(class_="author-meta"))
        return author_elements

    def _find_author_data(
        self,
        author_text: str,
        authors: list[dict[str, str]],
    ) -> Optional[dict[str, str]]:
        """Find author data by name.

        Args:
            author_text: Author text from HTML
            authors: List of author metadata

        Returns:
            Author data or None
        """
        author_text_lower = author_text.lower()

        for author in authors:
            computed_name = author.get("_computed_name", "")
            if computed_name.lower() in author_text_lower:
                return author

        return None

    def _inject_orcid_icon(
        self,
        soup: BeautifulSoup,
        element,
        orcid: str,
    ) -> bool:
        """Inject ORCID icon into element.

        Args:
            soup: BeautifulSoup object
            element: Element to inject into
            orcid: ORCID identifier

        Returns:
            True if injected, False otherwise
        """
        # Remove existing ORCID icons
        self._remove_existing_orcid_icons(element)

        # Check if there's already an ORCID link
        existing_link = element.find("a", href=lambda h: h and "orcid.org" in h)

        orcid_img = (
            f'<img src="{self.ORCID_SVG_URL}" alt="ORCID" '
            f'style="height:1em; vertical-align:middle; margin-left:0.25em;" />'
        )

        if existing_link:
            # Normalize existing link
            existing_link.clear()
            existing_link.append(BeautifulSoup(orcid_img, "html.parser"))
            existing_link["class"] = (existing_link.get("class") or []) + ["orcid-link"]
            existing_link["target"] = "_blank"
            existing_link["rel"] = "noopener noreferrer"
            existing_link["title"] = f"ORCID: {orcid}"
            existing_link["href"] = f"https://orcid.org/{orcid}"
            return True

        # Create new ORCID link
        orcid_url = f"https://orcid.org/{orcid}"
        orcid_link = soup.new_tag(
            "a",
            href=orcid_url,
            **{
                "class": "orcid-link",
                "target": "_blank",
                "rel": "noopener noreferrer",
                "title": f"ORCID: {orcid}",
            },
        )
        orcid_link.append(BeautifulSoup(orcid_img, "html.parser"))
        element.append(" ")
        element.append(orcid_link)

        logger.debug(f"Added ORCID icon for {orcid}")
        return True

    def _inject_scholia_link(
        self,
        soup: BeautifulSoup,
        element,
        qid: str,
    ) -> bool:
        """Inject Scholia link into element.

        Args:
            soup: BeautifulSoup object
            element: Element to inject into
            qid: Wikidata QID

        Returns:
            True if injected, False otherwise
        """
        # Check if already has Scholia link
        existing_link = element.find(
            "a",
            href=lambda h: h and "scholia.toolforge.org" in h,
        )
        if existing_link:
            return False

        scholia_url = f"https://scholia.toolforge.org/author/{qid}"
        scholia_img = (
            f'<img src="{self.SCHOLIA_SVG_URL}" alt="Scholia" '
            f'style="height:1em; vertical-align:middle; margin-left:0.25em;" />'
        )

        link = soup.new_tag(
            "a",
            href=scholia_url,
            **{
                "class": "scholia-link",
                "target": "_blank",
                "rel": "noopener noreferrer",
                "title": f"Scholia profile: {qid}",
            },
        )
        link.append(BeautifulSoup(scholia_img, "html.parser"))

        element.append(" ")
        element.append(link)

        logger.debug(f"Added Scholia link for {qid}")
        return True

    def _remove_existing_orcid_icons(self, element) -> None:
        """Remove existing ORCID icon elements.

        Args:
            element: Element to clean
        """
        # Remove icon tags
        for tag in element.find_all("i"):
            classes = tag.get("class", [])
            if (
                any(cls.startswith("ai") for cls in classes)
                or "orcid" in " ".join(classes).lower()
            ):
                tag.decompose()

        # Remove SVG tags
        for svg in element.find_all("svg"):
            aria_label = svg.get("aria-label", "")
            if "orcid" in aria_label.lower():
                svg.decompose()

        # Remove existing ORCID images
        for img in element.find_all("img"):
            src = (img.get("src") or "").lower()
            alt = (img.get("alt") or "").lower()
            if "orcid" in src or "orcid" in alt:
                img.decompose()

    def process_files(
        self,
        qmd_files: list[Path],
        site_dir: Path,
    ) -> int:
        """Process multiple QMD/HTML file pairs.

        Args:
            qmd_files: List of QMD source files
            site_dir: Site output directory

        Returns:
            Total number of enrichments made
        """
        total_enriched = 0

        for qmd_path in qmd_files:
            html_path = self.fs.get_html_path(qmd_path, str(site_dir))
            if self.fs.exists(html_path):
                enriched = self.inject_into_html(qmd_path, html_path)
                total_enriched += enriched
            else:
                logger.warning(f"HTML not found for {qmd_path.name}")

        logger.info(f"Enriched {total_enriched} authors across {len(qmd_files)} files")
        return total_enriched
