"""ROR (Research Organization Registry) service for affiliation linking."""

from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from infrastructure.filesystem import FileSystem
from infrastructure.html_processor import HtmlProcessor
from infrastructure.logger import get_logger
from infrastructure.yaml_loader import YamlLoader

logger = get_logger(__name__)


class RorService:
    """Handles ROR affiliation linking in HTML files."""

    # Official ROR and Scholia logos
    ROR_ICON_URL = (
        "https://raw.githubusercontent.com/ror-community/ror-logos/"
        "refs/heads/main/ror-icon-rgb-transparent.svg"
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
        """Initialize ROR service.

        Args:
            filesystem: FileSystem instance
            html_processor: HtmlProcessor instance
            yaml_loader: YamlLoader instance
        """
        self.fs = filesystem
        self.html = html_processor
        self.yaml = yaml_loader

    def load_affiliations(self, qmd_path: Path) -> dict[str, dict[str, str]]:
        """Load affiliation definitions from metadata files and QMD frontmatter.

        Args:
            qmd_path: Path to QMD file

        Returns:
            Dictionary mapping affiliation name -> {ror: url, qid: qid}
        """
        merged: dict[str, dict[str, str]] = {}

        # Load QMD frontmatter
        metadata = self.yaml.load_from_path(qmd_path)
        if not metadata:
            return merged

        # Load from metadata-files referenced in frontmatter
        metadata_files = metadata.get("metadata-files", [])
        if isinstance(metadata_files, list):
            for metadata_path in metadata_files:
                metadata_doc = self.yaml.load_metadata_file(
                    metadata_path,
                    qmd_path.parent,
                )
                if metadata_doc:
                    affiliations = self._parse_affiliations(metadata_doc)
                    merged.update(affiliations)

        # Apply affiliations from QMD frontmatter (overrides)
        merged.update(self._parse_affiliations(metadata))

        logger.debug(f"Loaded {len(merged)} affiliations for {qmd_path.name}")
        return merged

    def _parse_affiliations(self, doc: dict) -> dict[str, dict[str, str]]:
        """Parse affiliation definitions from a YAML document.

        Args:
            doc: YAML document dictionary

        Returns:
            Mapping of affiliation name -> {ror: url, qid: qid}
        """
        result: dict[str, dict[str, str]] = {}

        if not doc or not isinstance(doc, dict):
            return result

        # Handle both 'affiliations' (list) and 'affiliation' (singular)
        affiliations = doc.get("affiliations")
        if not affiliations:
            affiliation_single = doc.get("affiliation")
            if affiliation_single:
                affiliations = [affiliation_single]

        if not isinstance(affiliations, list):
            return result

        for aff in affiliations:
            if not isinstance(aff, dict):
                continue

            name = aff.get("name")
            if not name:
                continue

            aff_data = {}

            # Extract ROR
            ror = aff.get("ror")
            if ror:
                aff_data["ror"] = str(ror).strip()

            # Extract Wikidata QID
            qid = aff.get("qid")
            if qid:
                aff_data["qid"] = str(qid).strip()

            if aff_data:
                result[str(name).strip()] = aff_data

        return result

    def inject_into_html(
        self,
        qmd_path: Path,
        html_path: Path,
    ) -> int:
        """Inject ROR and Scholia links into HTML affiliation paragraphs.

        Args:
            qmd_path: Path to QMD source file
            html_path: Path to HTML output file

        Returns:
            Number of affiliations enriched with links
        """
        # Load affiliation definitions
        aff_dict = self.load_affiliations(qmd_path)
        if not aff_dict:
            logger.debug(f"No affiliations found for {qmd_path.name}")
            return 0

        # Load HTML
        soup = self.html.load_from_path(html_path)
        if soup is None:
            return 0

        # Inject links
        enriched_count = self._inject_links(soup, aff_dict)

        # Save if changed
        if enriched_count > 0:
            self.html.save_to_path(soup, html_path)
            logger.info(
                f"✓ Injected ROR links for {enriched_count} affiliation(s) "
                f"in {html_path.name}",
            )

        return enriched_count

    def _inject_links(
        self,
        soup: BeautifulSoup,
        aff_dict: dict[str, dict[str, str]],
    ) -> int:
        """Inject ROR and Scholia links into affiliation elements.

        Args:
            soup: BeautifulSoup object
            aff_dict: Affiliation data dictionary

        Returns:
            Number of affiliations enriched
        """
        enriched_count = 0

        # Find affiliation paragraphs
        affiliation_elements = []
        for p in soup.find_all("p"):
            classes = p.get("class", [])
            if any("affiliation" in str(cls).lower() for cls in classes):
                affiliation_elements.append(p)

        for aff_elem in affiliation_elements:
            # Skip if already has ROR link
            existing_link = aff_elem.find(
                "a",
                class_="uri",
                href=lambda h: h and "ror.org" in h,
            )
            if existing_link:
                continue

            # Get affiliation text
            aff_text = aff_elem.get_text().strip()

            # Find matching affiliation data (case-insensitive)
            aff_data = self._find_affiliation_data(aff_text, aff_dict)

            if aff_data:
                # Add ROR link
                ror_url = aff_data.get("ror")
                if ror_url:
                    self._add_ror_link(soup, aff_elem, ror_url)
                    enriched_count += 1

                # Add Scholia link
                qid = aff_data.get("qid")
                if qid:
                    self._add_scholia_link(soup, aff_elem, qid)
                    enriched_count += 1

        return enriched_count

    def _find_affiliation_data(
        self,
        aff_text: str,
        aff_dict: dict[str, dict[str, str]],
    ) -> Optional[dict[str, str]]:
        """Find affiliation data by name (case-insensitive).

        Args:
            aff_text: Affiliation text from HTML
            aff_dict: Affiliation data dictionary

        Returns:
            Affiliation data or None
        """
        # Exact match
        if aff_text in aff_dict:
            return aff_dict[aff_text]

        # Case-insensitive match
        aff_text_lower = aff_text.lower()
        for name, data in aff_dict.items():
            if name.lower() == aff_text_lower:
                return data

        return None

    def _add_ror_link(
        self,
        soup: BeautifulSoup,
        element,
        ror_url: str,
    ) -> None:
        """Add ROR link to element.

        Args:
            soup: BeautifulSoup object
            element: Element to add link to
            ror_url: ROR URL
        """
        ror_img = (
            f'<img src="{self.ROR_ICON_URL}" alt="" aria-hidden="true" '
            f'style="height:14px; vertical-align:middle;" />'
        )

        link = soup.new_tag(
            "a",
            href=ror_url,
            **{
                "class": "uri",
                "aria-label": "View organization in Research Organization Registry (ROR)",
                "target": "_blank",
                "rel": "noopener noreferrer",
            },
        )
        link.append(BeautifulSoup(ror_img, "html.parser"))

        element.append(" ")
        element.append(link)

    def _add_scholia_link(
        self,
        soup: BeautifulSoup,
        element,
        qid: str,
    ) -> None:
        """Add Scholia link to element.

        Args:
            soup: BeautifulSoup object
            element: Element to add link to
            qid: Wikidata QID
        """
        scholia_url = f"https://scholia.toolforge.org/organization/{qid}"
        scholia_img = (
            f'<img src="{self.SCHOLIA_SVG_URL}" alt="" aria-hidden="true" '
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
                "aria-label": f"View Scholia profile for {qid}",
            },
        )
        link.append(BeautifulSoup(scholia_img, "html.parser"))

        element.append(" ")
        element.append(link)

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
            Total number of affiliations enriched
        """
        total_enriched = 0

        for qmd_path in qmd_files:
            html_path = self.fs.get_html_path(qmd_path, str(site_dir))
            if self.fs.exists(html_path):
                enriched = self.inject_into_html(qmd_path, html_path)
                total_enriched += enriched
            else:
                logger.warning(f"HTML not found for {qmd_path.name}")

        logger.info(
            f"Enriched {total_enriched} affiliations across {len(qmd_files)} files",
        )
        return total_enriched
